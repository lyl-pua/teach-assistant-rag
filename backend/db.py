# -*- coding: utf-8 -*-
"""
SQLite 数据库模块
- 使用 sqlite3 原生 + 连接池（check_same_thread=False）
- 首次运行自动建表
"""
import os
import sqlite3
import json
import threading
from contextlib import contextmanager
from datetime import datetime

import config

# 数据目录
_DATA_DIR = os.path.dirname(config.DB_PATH)
os.makedirs(_DATA_DIR, exist_ok=True)
os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)

# ============ 连接管理 ============
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


@contextmanager
def get_cursor(commit: bool = False):
    conn = _get_conn()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


# ============ 建表 ============
_CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS inbox_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT DEFAULT '',
        type TEXT NOT NULL DEFAULT 'note',  -- note|idea|todo|student
        tags TEXT DEFAULT '',
        pinned INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT DEFAULT '',
        date TEXT NOT NULL,               -- YYYY-MM-DD
        time_start TEXT DEFAULT '',
        time_end TEXT DEFAULT '',
        category TEXT NOT NULL DEFAULT 'life',  -- teach|research|meeting|life|student
        done INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        category TEXT DEFAULT '',
        file_path TEXT NOT NULL,
        file_size INTEGER DEFAULT 0,
        chunks_count INTEGER DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'processing', -- processing|ready|error
        meta TEXT DEFAULT '{}',            -- JSON
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL DEFAULT 0,
        text TEXT NOT NULL,
        meta TEXT DEFAULT '{}',
        FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT DEFAULT '新会话',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        role TEXT NOT NULL,               -- user|assistant
        content TEXT NOT NULL,
        refs TEXT DEFAULT '[]',           -- JSON
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tool_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_type TEXT NOT NULL,          -- lesson_plan|courseware|homework|paper
        title TEXT DEFAULT '',
        prompt TEXT DEFAULT '',
        result TEXT DEFAULT '{}',         -- JSON
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
]

# 默认 settings（首次初始化）
_DEFAULT_SETTINGS = {
    "user_name": "刘老师",
    "default_city": "汉寿",
    "city_lat": "28.914",
    "city_lon": "111.976",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_db() -> None:
    """初始化数据库：建表 + 写入默认 settings"""
    with get_cursor(commit=True) as cur:
        for sql in _CREATE_TABLES_SQL:
            cur.execute(sql)
        # 写入默认 settings（若不存在）
        for k, v in _DEFAULT_SETTINGS.items():
            cur.execute("SELECT 1 FROM settings WHERE key = ?", (k,))
            if not cur.fetchone():
                cur.execute("INSERT INTO settings(key, value) VALUES(?, ?)", (k, v))
    # 让 config 模块从 DB 加载
    config.reload_settings_from_db()


# ============ Settings 快捷函数 ============
# 兼容字典：前端常以小写命名保存（如 deepseek_api_key），后端统一归一成 config.RELOADABLE_SETTINGS 里的大写键名，
# 保证 reload_settings_from_db 能按大写键读到。
_KEY_NORMALIZE = {
    "deepseek_api_key": "DEEPSEEK_API_KEY",
    "openai_api_key":   "OPENAI_API_KEY",
    "zhipu_api_key":    "ZHIPU_API_KEY",
    "glm_api_key":      "GLM_API_KEY",
    "city_latitude":    "city_lat",
    "city_longitude":   "city_lon",
}


def _normalize_key(key: str) -> str:
    if not key:
        return key
    k = key.strip()
    # 1) 显式别名映射
    if k in _KEY_NORMALIZE:
        return _KEY_NORMALIZE[k]
    # 2) 若 RELOADABLE_SETTINGS 已包含该 key（大小写），优先返回其标准写法
    for sk in config.RELOADABLE_SETTINGS.keys():
        if sk.lower() == k.lower():
            return sk
    return k


def get_setting(key: str, default=None):
    try:
        with get_cursor() as cur:
            k = _normalize_key(key)
            cur.execute("SELECT value FROM settings WHERE key = ?", (k,))
            row = cur.fetchone()
            if row:
                return row["value"]
            # 兜底：如果用户把老的键名以非标准形式写入 DB，再按原 key 查一次
            if k != key:
                cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cur.fetchone()
                return row["value"] if row else default
            return default
    except Exception:
        return default


def set_setting(key: str, value) -> None:
    """写入或更新 setting，更新后让 config reload。
    写入时统一用规范化后的大写键名，避免前端小写/后端大写不一致导致『已配置但读不到』。"""
    k = _normalize_key(key)
    v = str(value)
    with get_cursor(commit=True) as cur:
        # 同时清理"同名但大小写不一致"的脏记录（如 DB 里原有 deepseek_api_key 小写记录，现在统一写成大写）
        if k != key:
            cur.execute("DELETE FROM settings WHERE key = ?", (key,))
        cur.execute("SELECT 1 FROM settings WHERE key = ?", (k,))
        if cur.fetchone():
            cur.execute("UPDATE settings SET value = ? WHERE key = ?", (v, k))
        else:
            cur.execute("INSERT INTO settings(key, value) VALUES(?, ?)", (k, v))
    # 同步更新缓存
    config.RELOADABLE_SETTINGS[k] = v
    # 保险：触发一次完整 reload（按大写键名全量覆盖）
    try:
        config.reload_settings_from_db()
    except Exception:
        pass


def list_settings() -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT key, value FROM settings")
        rows = cur.fetchall()
    raw = {r["key"]: r["value"] for r in rows}
    # 归一化输出：把 DB 里仍存在的小写别名键统一翻译成大写标准键（去重后以大写为准）
    out = {}
    for k, v in raw.items():
        nk = _normalize_key(k)
        if nk not in out:
            out[nk] = v
    # 再追加 RELOADABLE_SETTINGS 里的默认键（若仍缺失），让前端 GET /settings 看到完整结构
    for sk in config.RELOADABLE_SETTINGS.keys():
        if sk not in out:
            out[sk] = config.RELOADABLE_SETTINGS.get(sk, "")
    return out


# ============ 通用工具 ============
def row_to_dict(row: sqlite3.Row) -> dict:
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


def json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def json_loads(s: str):
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None
