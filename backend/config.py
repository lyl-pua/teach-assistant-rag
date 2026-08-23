# -*- coding: utf-8 -*-
"""
全局配置模块
- API Key 优先级：SQLite settings 表 > 环境变量
- 支持运行时 reload（settings 更新后）
"""
import os
from dotenv import load_dotenv

# 加载 .env（可选，主要作为兜底）
load_dotenv()

# ============ 可热加载的 settings（与 settings 表 key 对应）============
# 注意：数据库首次初始化时会写默认值
RELOADABLE_SETTINGS = {
    # 大模型 API Key（通用 ChatCompletions，sk- 前缀）
    "DEEPSEEK_API_KEY": "",
    "OPENAI_API_KEY": "",
    # 智谱 AI（embedding + chat）
    "ZHIPU_API_KEY": "",
    "GLM_API_KEY": "",
    # 和风天气 Web API Key（可选，未配置则使用 Open-Meteo 主源）
    "HEFENG_API_KEY": "",
    # 用户/城市
    "user_name": "刘老师",
    "default_city": "汉寿",
    "city_lat": "28.914",
    "city_lon": "111.976",
}

# 是否已经从 DB 加载过一次
_DB_LOADED = False


def _safe_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def reload_settings_from_db() -> None:
    """从 SQLite settings 表重新加载所有 Key。必须在 db 初始化后调用。"""
    global _DB_LOADED
    try:
        from db import get_setting
        for key in list(RELOADABLE_SETTINGS.keys()):
            v = get_setting(key, default=None)
            if v is not None:
                RELOADABLE_SETTINGS[key] = _safe_str(v)
        _DB_LOADED = True
    except Exception:
        # 首次启动时 db 可能还没建好，跳过即可
        pass


def get_env_or_db(key: str, default: str = "") -> str:
    """
    获取配置：优先 DB(settings 表)，其次环境变量，最后 default
    """
    # 1) 尝试从 DB（RELOADABLE_SETTINGS 缓存）
    db_val = RELOADABLE_SETTINGS.get(key, None)
    if db_val not in (None, ""):
        return _safe_str(db_val)
    # 2) 环境变量
    env_val = os.environ.get(key, "")
    if env_val:
        return _safe_str(env_val)
    # 3) 大小写不敏感再查一次
    for k in (key.upper(), key.lower()):
        v = os.environ.get(k, "")
        if v:
            return _safe_str(v)
    return default


# ================ 对外快捷访问 ================
def get_deepseek_key() -> str:
    return get_env_or_db("DEEPSEEK_API_KEY", "") or get_env_or_db("OPENAI_API_KEY", "")


def get_sk_key() -> str:
    """任何 sk-* 前缀的通用 Chat Key（DeepSeek 或 OpenAI 兼容）"""
    k = get_deepseek_key()
    return k if k.startswith("sk-") else ""


def get_zhipu_key() -> str:
    return get_env_or_db("ZHIPU_API_KEY", "") or get_env_or_db("GLM_API_KEY", "")


def has_any_llm_key() -> bool:
    return bool(get_sk_key() or get_zhipu_key())


def has_any_embed_key() -> bool:
    return bool(get_zhipu_key())


def get_user_name() -> str:
    return get_env_or_db("user_name", "刘老师")


def get_default_city() -> tuple[str, float, float]:
    city = get_env_or_db("default_city", "汉寿")
    try:
        lat = float(get_env_or_db("city_lat", "28.914"))
    except Exception:
        lat = 28.914
    try:
        lon = float(get_env_or_db("city_lon", "111.976"))
    except Exception:
        lon = 111.976
    return city, lat, lon


# ================ 常量 ================
APP_VERSION = "2.0.0"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db")
VECTORSTORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vectorstore.pkl")
DOCUMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "documents")

# 智谱 embedding-3 实际维度 2048（v2025+；如用 embedding-2 改为 1024）
EMBEDDING_DIM = 2048
# 分块参数
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

# ================ Token 优化参数 ================
# 检索 score 阈值：低于此值的 chunk 视为不相关，不注入 prompt（省 token）
RETRIEVAL_SCORE_THRESHOLD = 0.30
# 单个 chunk 注入 prompt 时的最大字符数（避免长 chunk 吃满 token）
CHUNK_TEXT_MAX_CHARS = 500
# LLM 查询缓存时间（秒）：相同 prompt 在此时间内直接返回缓存结果
LLM_CACHE_TTL = 300
