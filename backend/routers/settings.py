# -*- coding: utf-8 -*-
"""
设置、连通性测试、导出数据、重建知识库
"""
import io
import time
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
from db import (
    get_cursor,
    get_setting,
    set_setting,
    list_settings,
    rows_to_list,
    json_dumps,
    json_loads,
)

router = APIRouter(prefix="")


class SettingPut(BaseModel):
    key: str
    value: str


class TestLLM(BaseModel):
    provider: str = "deepseek"  # deepseek | zhipu | dashscope


def _mask_key(k: str, v: str) -> str:
    k_lower = k.lower()
    if "api_key" in k_lower or "password" in k_lower or "secret" in k_lower:
        if not v:
            return ""
        tail = v[-6:] if len(v) >= 6 else v
        return f"****{tail}"
    return v


# ============ GET / PUT ============
@router.get("/settings")
def get_all_settings():
    raw = list_settings()
    return {k: _mask_key(k, v) for k, v in raw.items()}


@router.put("/settings")
def put_setting(body: SettingPut):
    if not body.key or not body.key.strip():
        raise HTTPException(400, "key 不能为空")
    key = body.key.strip()
    value = body.value or ""
    set_setting(key, value)
    # reload config
    try:
        config.reload_settings_from_db()
    except Exception:
        pass
    return {"ok": True, "key": key, "value": _mask_key(key, value)}


# ============ 测试 ============
@router.post("/settings/test-llm")
def test_llm(body: TestLLM):
    # 每次都强制从 DB reload（解决 "DB 有 Key 但内存为空" 的时序问题）
    try:
        config.reload_settings_from_db()
    except Exception:
        pass
    provider = (body.provider or "deepseek").lower()
    if provider not in {"deepseek", "zhipu", "dashscope"}:
        raise HTTPException(400, "provider 必须是 deepseek / zhipu / dashscope 之一")
    # 校验是否有对应 key
    if provider == "deepseek":
        if not config.get_sk_key():
            return {"success": False, "error": f"未配置 DeepSeek/OpenAI sk-* API Key（DB已载入的Key长度={len(config.get_env_or_db('DEEPSEEK_API_KEY','') or config.get_env_or_db('OPENAI_API_KEY',''))}）", "latency_ms": 0}
    elif provider == "zhipu":
        if not config.get_zhipu_key():
            return {"success": False, "error": f"未配置 Zhipu/GLM API Key（DB已载入的Key长度={len(config.get_env_or_db('ZHIPU_API_KEY','') or config.get_env_or_db('GLM_API_KEY',''))}）", "latency_ms": 0}
    else:  # dashscope
        if not config.get_dashscope_key():
            return {"success": False, "error": f"未配置 Qianwen/DashScope API Key（DB已载入的Key长度={len(config.get_env_or_db('DASHSCOPE_API_KEY','') or config.get_env_or_db('QWEN_API_KEY',''))}）", "latency_ms": 0}

    import requests

    if provider == "deepseek":
        url = "https://api.deepseek.com/v1/chat/completions"
        model = "deepseek-chat"
        key = config.get_sk_key()
    elif provider == "zhipu":
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        model = "glm-4-flash"
        key = config.get_zhipu_key()
    else:  # dashscope：用 compatible-mode /v1/models 做免费、快速的鉴权连通测试
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/models"
        model = "(list-models 鉴权)"
        key = config.get_dashscope_key()

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    if provider == "dashscope":
        # DashScope：GET /models 即可完成连通性+鉴权验证（不消耗token）
        t0 = time.time()
        try:
            resp = requests.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=60)
            dt_ms = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                return {
                    "success": False,
                    "latency_ms": dt_ms,
                    "model_used": model,
                    "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                }
            data = resp.json()
            count = len(data.get("data", []) or []) if isinstance(data, dict) else 0
            return {
                "success": True,
                "latency_ms": dt_ms,
                "model_used": model,
                "echo": f"✅ DashScope 连通正常，账户可用模型数量: {count}",
            }
        except Exception as e:
            return {"success": False, "latency_ms": int((time.time() - t0) * 1000), "error": str(e)}

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请回复 OK（只回复这两个字）"}],
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 50,
    }
    t0 = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        dt_ms = int((time.time() - t0) * 1000)
        if resp.status_code != 200:
            return {
                "success": False,
                "latency_ms": dt_ms,
                "model_used": model,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return {
            "success": "ok" in content.lower(),
            "latency_ms": dt_ms,
            "model_used": model,
            "echo": content[:100],
        }
    except Exception as e:
        return {"success": False, "latency_ms": int((time.time() - t0) * 1000), "error": str(e)}


@router.post("/settings/test-embed")
def test_embed():
    try:
        config.reload_settings_from_db()
    except Exception:
        pass
    if not config.has_any_embed_key():
        cur_len = len(config.get_env_or_db('ZHIPU_API_KEY','') or config.get_env_or_db('GLM_API_KEY',''))
        return {"success": False, "dim": 0, "latency_ms": 0, "error": f"未配置 Zhipu/GLM API Key（DB已载入的Key长度={cur_len}）"}
    t0 = time.time()
    try:
        from rag.embeddings import ZhipuEmbedding
        emb = ZhipuEmbedding()
        # 强制真正调用：如果用了伪向量，那就算作 pseudo 成功
        # 这里先判断有无 key 再走真调用
        # ZhipuEmbedding.embed 已经会根据 has_any_embed_key 分支；为了真测，直接手工调用 _call_batch
        key = config.get_zhipu_key()
        if not key:
            return {"success": False, "dim": 0, "latency_ms": 0, "error": "未配置 Zhipu/GLM API Key"}
        import requests as rq
        resp = rq.post(
            "https://open.bigmodel.cn/api/paas/v4/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "embedding-3", "input": ["测试"]},
            timeout=60,
        )
        dt_ms = int((time.time() - t0) * 1000)
        if resp.status_code != 200:
            return {"success": False, "dim": 0, "latency_ms": dt_ms, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        vec = data["data"][0]["embedding"]
        return {"success": True, "dim": len(vec), "latency_ms": dt_ms, "provider": "zhipu"}
    except Exception as e:
        return {"success": False, "dim": 0, "latency_ms": int((time.time() - t0) * 1000), "error": str(e)}


# ============ 重建知识库 ============
@router.post("/settings/rebuild-kb")
def rebuild_kb():
    """对所有 status=ready 的文档重新分块 + embedding + 写 vectorstore"""
    import os
    from rag.parser import parse_and_chunk
    from rag.embeddings import ZhipuEmbedding
    from rag.vectorstore import reset_vector_store, get_vector_store

    # 1) 找出所有 ready 文档
    with get_cursor() as cur:
        cur.execute("SELECT id, filename, category, file_path FROM documents WHERE status = 'ready' ORDER BY id ASC")
        docs = rows_to_list(cur.fetchall())

    processed = 0
    total_chunk_ids: list[int] = []
    total_chunk_texts: list[str] = []
    total_metas: list[dict] = []

    for d in docs:
        doc_id = d["id"]
        filename = d["filename"]
        category = d.get("category") or ""
        file_path = d.get("file_path") or ""
        if not file_path or not os.path.exists(file_path):
            continue
        # 解析
        try:
            _ft, chunks = parse_and_chunk(file_path)
        except Exception:
            continue
        # 重写 chunks 表
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            local_ids: list[int] = []
            for idx, text in enumerate(chunks):
                cur.execute(
                    "INSERT INTO chunks(doc_id, chunk_index, text, meta) VALUES(?,?,?,?)",
                    (doc_id, idx, text, "{}"),
                )
                local_ids.append(int(cur.lastrowid))
            cur.execute(
                "UPDATE documents SET chunks_count = ? WHERE id = ?",
                (len(chunks), doc_id),
            )
        # 收集全局 embedding
        for i, cid in enumerate(local_ids):
            total_chunk_ids.append(cid)
            total_chunk_texts.append(chunks[i])
            total_metas.append({
                "doc_id": doc_id,
                "doc_name": filename,
                "chunk_index": i,
                "category": category,
            })
        processed += 1

    # 2) 重置向量库并 embedding 所有
    vs = reset_vector_store()
    if total_chunk_ids:
        embed = ZhipuEmbedding()
        vecs = embed.embed(total_chunk_texts)
        vs.add(vecs, total_chunk_ids, total_metas)
    try:
        vs.save(config.VECTORSTORE_PATH)
    except Exception:
        pass
    return {
        "rebuilt": True,
        "docs_processed": processed,
        "total_chunks": vs.total_chunks,
    }


# ============ 导出数据 ============
@router.get("/settings/export-data")
def export_data():
    """导出 JSON（安全：API Key 脱敏）。"""
    with get_cursor() as cur:
        # inbox
        cur.execute("SELECT * FROM inbox_items ORDER BY id DESC LIMIT 5000")
        inbox = rows_to_list(cur.fetchall())
        # schedule
        cur.execute("SELECT * FROM schedules ORDER BY date DESC, id DESC LIMIT 5000")
        schedules = rows_to_list(cur.fetchall())
        # doc list meta（不返回 content/file 内容）
        cur.execute("SELECT id, filename, category, file_size, chunks_count, status, created_at FROM documents ORDER BY id DESC")
        doc_list = rows_to_list(cur.fetchall())
        # settings safe
        cur.execute("SELECT key, value FROM settings")
        settings_safe = {r["key"]: _mask_key(r["key"], r["value"]) for r in cur.fetchall()}
        # sessions summary（不含消息正文）
        cur.execute(
            """SELECT s.id, s.title, s.created_at, s.updated_at,
               (SELECT COUNT(*) FROM chat_messages m WHERE m.session_id=s.id) as msg_count
               FROM chat_sessions s ORDER BY s.id DESC LIMIT 1000"""
        )
        sessions_summary = rows_to_list(cur.fetchall())
        # tool_runs（含 markdown 结果，不含 prompt 中可能的 key，实际上 prompt 也没 key）
        cur.execute("SELECT * FROM tool_runs ORDER BY id DESC LIMIT 2000")
        tool_runs = rows_to_list(cur.fetchall())
        for t in tool_runs:
            if t.get("result"):
                t["result"] = json_loads(t["result"]) or {}

    return {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "app_version": config.APP_VERSION,
        "inbox": inbox,
        "schedules": schedules,
        "doc_list_meta": doc_list,
        "settings_safe": settings_safe,
        "sessions_summary": sessions_summary,
        "tool_runs": tool_runs,
    }
