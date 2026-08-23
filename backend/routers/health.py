# -*- coding: utf-8 -*-
"""
健康检查 / 统计端点
"""
from datetime import datetime

from fastapi import APIRouter

import config
from db import get_cursor
from rag.vectorstore import get_vector_store

router = APIRouter(prefix="")


def _greeting(user_name: str) -> str:
    h = datetime.now().hour
    if 5 <= h < 12:
        t = "早上好"
    elif 12 <= h < 14:
        t = "中午好"
    elif 14 <= h < 18:
        t = "下午好"
    else:
        t = "晚上好"
    # 去掉最后一个"老师"再拼（如 "刘老师"→"刘老师"）
    suffix = "" if "老师" in user_name else "老师"
    return f"{t}，{user_name}{suffix}！"


def _count_from(sql: str, params: tuple = ()) -> int:
    try:
        with get_cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


@router.get("/health")
def health():
    # 每次请求都强制从 DB 重新加载 Key（解决"DB 有 Key 但内存为空"）
    try:
        config.reload_settings_from_db()
    except Exception:
        pass
    user_name = config.get_user_name()
    vs = get_vector_store()
    total_docs = _count_from("SELECT COUNT(*) FROM documents")
    return {
        "ok": True,
        "version": config.APP_VERSION,
        "user_name": user_name,
        "greeting": _greeting(user_name),
        "has_llm_key": config.has_any_llm_key(),
        "has_embed_key": config.has_any_embed_key(),
        "vector_stats": {
            "total_chunks": vs.total_chunks,
            "total_docs": vs.total_docs() if hasattr(vs, "total_docs") else total_docs,
            "embedding_dim": getattr(vs, "dim", config.EMBEDDING_DIM),
        },
    }


@router.get("/stats")
def stats():
    try:
        config.reload_settings_from_db()
    except Exception:
        pass
    # 基础计数
    inbox_count = _count_from("SELECT COUNT(*) FROM inbox_items")
    pinned_count = _count_from("SELECT COUNT(*) FROM inbox_items WHERE pinned = 1")
    schedule_count = _count_from("SELECT COUNT(*) FROM schedules")
    schedule_done = _count_from("SELECT COUNT(*) FROM schedules WHERE done = 1")
    doc_count = _count_from("SELECT COUNT(*) FROM documents")
    doc_ready = _count_from("SELECT COUNT(*) FROM documents WHERE status = 'ready'")
    kb_chunks = _count_from("SELECT COUNT(*) FROM chunks")
    chat_sessions = _count_from("SELECT COUNT(*) FROM chat_sessions")
    chat_messages = _count_from("SELECT COUNT(*) FROM chat_messages")
    tool_runs = _count_from("SELECT COUNT(*) FROM tool_runs")

    # 7 天内 tool_runs
    from datetime import timedelta
    since = (datetime.now() - timedelta(days=7)).isoformat()
    tool_runs_7d = _count_from(
        "SELECT COUNT(*) FROM tool_runs WHERE created_at >= ?", (since,)
    )

    # 各类型分布
    tool_by_type = {}
    try:
        with get_cursor() as cur:
            cur.execute("SELECT tool_type, COUNT(*) FROM tool_runs GROUP BY tool_type")
            for r in cur.fetchall():
                tool_by_type[r[0]] = int(r[1])
    except Exception:
        pass

    # 向量库统计
    vs = get_vector_store()
    return {
        "inbox_count": inbox_count,
        "inbox_pinned": pinned_count,
        "schedule_count": schedule_count,
        "schedule_done": schedule_done,
        "doc_count": doc_count,
        "doc_ready": doc_ready,
        "kb_chunks": kb_chunks,
        "kb_vector_chunks": vs.total_chunks,
        "chat_sessions": chat_sessions,
        "chat_messages": chat_messages,
        "tool_runs": tool_runs,
        "tool_runs_7d": tool_runs_7d,
        "tool_runs_by_type": tool_by_type,
        "has_llm_key": config.has_any_llm_key(),
        "has_embed_key": config.has_any_embed_key(),
        "embedding_dim": getattr(vs, "dim", config.EMBEDDING_DIM),
    }


@router.get("/stats/tokens")
def token_stats():
    """Token 用量统计"""
    try:
        from rag.generator import get_token_stats
        return get_token_stats()
    except Exception as e:
        return {"total": {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "by_model": [], "recent": [], "error": str(e)}


@router.get("/stats/cache")
def cache_stats():
    """LLM 查询缓存统计（Token 优化）"""
    try:
        from rag.generator import get_cache_stats
        return get_cache_stats()
    except Exception as e:
        return {"total_entries": 0, "valid_entries": 0, "ttl_seconds": 300, "error": str(e)}


@router.post("/cache/clear")
def cache_clear():
    """清空 LLM 查询缓存"""
    try:
        from rag.generator import clear_llm_cache
        n = clear_llm_cache()
        return {"cleared": True, "removed": n}
    except Exception as e:
        return {"cleared": False, "error": str(e)}
