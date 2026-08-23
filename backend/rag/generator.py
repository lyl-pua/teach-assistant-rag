# -*- coding: utf-8 -*-
"""
LLM 生成器封装
- 优先 DeepSeek (sk-*)，兜底智谱 glm-4-flash
- 非流式调用
"""
import json
import time
from typing import Optional

import requests

import config

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

ZHIPU_CHAT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_MODEL = "glm-4-flash"
ZHIPU_LONG_MODEL = "glm-4"


def _record_token_usage(usage: dict):
    """将每次 LLM 调用的 token 用量写入 DB"""
    import sqlite3
    db_path = config.DB_PATH
    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            provider TEXT,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            latency_ms INTEGER
        )
    """)
    cur.execute(
        "INSERT INTO token_usage(ts,provider,model,prompt_tokens,completion_tokens,total_tokens,latency_ms) VALUES(?,?,?,?,?,?,?)",
        (
            usage.get("ts", ""),
            usage.get("provider", ""),
            usage.get("model", ""),
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            int(usage.get("total_tokens", 0)),
            int(usage.get("latency_ms", 0)),
        ),
    )
    conn.commit()
    conn.close()


def get_token_stats() -> dict:
    """聚合查询 token 用量统计"""
    import sqlite3
    db_path = config.DB_PATH
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # 总量
    cur.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(prompt_tokens),0) as pt, COALESCE(SUM(completion_tokens),0) as ct, COALESCE(SUM(total_tokens),0) as tt FROM token_usage")
    row = cur.fetchone()
    total = {"calls": row["cnt"], "prompt_tokens": row["pt"], "completion_tokens": row["ct"], "total_tokens": row["tt"]}
    # 按模型分组
    cur.execute("SELECT model, COUNT(*) as cnt, SUM(total_tokens) as tt, SUM(prompt_tokens) as pt, SUM(completion_tokens) as ct FROM token_usage GROUP BY model ORDER BY tt DESC")
    by_model = []
    for r in cur.fetchall():
        by_model.append({"model": r["model"], "calls": r["cnt"], "total_tokens": r["tt"], "prompt_tokens": r["pt"], "completion_tokens": r["ct"]})
    # 最近5条
    cur.execute("SELECT ts,provider,model,prompt_tokens,completion_tokens,total_tokens,latency_ms FROM token_usage ORDER BY id DESC LIMIT 5")
    recent = []
    for r in cur.fetchall():
        recent.append({"ts": r["ts"], "provider": r["provider"], "model": r["model"], "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"], "total_tokens": r["total_tokens"], "latency_ms": r["latency_ms"]})
    conn.close()
    return {"total": total, "by_model": by_model, "recent": recent}


def _provider_info() -> tuple[str, str, str]:
    """返回 (provider, endpoint, model)"""
    sk = config.get_sk_key()
    if sk:
        return "deepseek", DEEPSEEK_URL, DEEPSEEK_MODEL
    zk = config.get_zhipu_key()
    if zk:
        return "zhipu", ZHIPU_CHAT_URL, ZHIPU_MODEL
    raise RuntimeError("未配置任何 LLM API Key（deepseek/openai/zhipu/glm）")


class LLMGenerator:
    """同步 Chat Completions 封装。若未配置 Key，在 chat() 抛异常，由上层降级。"""

    def __init__(self):
        self.last_usage = None  # {"provider":"","model":"","prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"ts":""}

    # 暴露给外面看用的
    def current_provider(self) -> str:
        try:
            return _provider_info()[0]
        except Exception:
            return "none"

    def current_model(self) -> str:
        try:
            return _provider_info()[2]
        except Exception:
            return "none"

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        timeout: int = 120,
    ) -> str:
        provider, endpoint, model = _provider_info()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        if provider == "deepseek":
            key = config.get_sk_key()
        else:
            key = config.get_zhipu_key()
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        t0 = time.time()
        resp = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM {provider} HTTP {resp.status_code} ({time.time()-t0:.1f}s): {resp.text[:300]}"
            )
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"LLM 返回结构异常: {json.dumps(data, ensure_ascii=False)[:300]}") from e

        # 捕获 token 用量
        usage = data.get("usage", {})
        self.last_usage = {
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": int((time.time() - t0) * 1000),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 持久化到 DB
        try:
            _record_token_usage(self.last_usage)
        except Exception:
            pass

        return content or ""


# 全局单例
GENERATOR = LLMGenerator()
