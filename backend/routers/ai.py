# -*- coding: utf-8 -*-
"""
AI 对话路由
- 会话 CRUD + 消息
- /ai/ask 同步 RAG
- /ai/stream SSE 流式
"""
import json
import time
from datetime import datetime
from typing import Optional, List, AsyncIterable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from db import (
    get_cursor,
    rows_to_list,
    json_dumps,
    json_loads,
    row_to_dict,
)
from rag.workflow import RAG_GRAPH
from rag.generator import GENERATOR

router = APIRouter(prefix="")


class AskBody(BaseModel):
    question: str
    top_k: int = 3
    session_id: Optional[int] = None
    stream: Optional[bool] = False  # 预留


class SessionCreate(BaseModel):
    title: str = "新会话"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _save_message(session_id: int, role: str, content: str, refs=None):
    if refs is None:
        refs = []
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO chat_messages(session_id, role, content, refs, created_at) VALUES(?,?,?,?,?)",
            (session_id, role, content, json_dumps(refs), _now()),
        )
        cur.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (_now(), session_id),
        )


# ================= 会话 =================
@router.get("/sessions")
def list_sessions():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC, id DESC LIMIT 500")
        return rows_to_list(cur.fetchall())


@router.post("/sessions")
def create_session(data: SessionCreate):
    now = _now()
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO chat_sessions(title, created_at, updated_at) VALUES(?,?,?)",
            (data.title or "新会话", now, now),
        )
        return {"id": cur.lastrowid, "title": data.title or "新会话", "created_at": now}


@router.delete("/sessions/{sid}")
def delete_session(sid: int):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM chat_sessions WHERE id = ?", (sid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "不存在的会话")
    return {"deleted": True}


@router.get("/sessions/{sid}/messages")
def list_messages(sid: int):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM chat_sessions WHERE id = ?", (sid,))
        if not cur.fetchone():
            raise HTTPException(404, "不存在的会话")
        cur.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
            (sid,),
        )
        rows = rows_to_list(cur.fetchall())
    for m in rows:
        if m.get("refs"):
            m["refs"] = json_loads(m["refs"]) or []
    return rows


@router.post("/sessions/{sid}/messages")
def append_message(sid: int, request: Request):
    # 简化：直接接收 JSON body {role, content, refs?}
    import json as _json
    try:
        raw = _json.loads((yield from request.body()) or b"{}")
    except Exception:
        raise HTTPException(400, "非法 JSON")
    # 这里为兼容 FastAPI 的同步函数，用更稳妥的方法：定义 Pydantic model
    return {"ok": False, "note": "请改用 /sessions/{sid}/messages_v2 或 /ai/ask"}


class MsgAppend(BaseModel):
    role: str = "user"
    content: str
    refs: Optional[list] = None


@router.post("/sessions/{sid}/messages_v2")
def append_message_v2(sid: int, data: MsgAppend):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM chat_sessions WHERE id = ?", (sid,))
        if not cur.fetchone():
            raise HTTPException(404, "不存在的会话")
    if data.role not in {"user", "assistant"}:
        raise HTTPException(400, "role 必须是 user 或 assistant")
    _save_message(sid, data.role, data.content or "", data.refs or [])
    return {"ok": True}


# ================= AI Ask =================
@router.post("/ai/ask")
def ai_ask(body: AskBody):
    if not body.question or not body.question.strip():
        raise HTTPException(400, "question 不能为空")

    top_k = max(1, min(int(body.top_k or 3), 20))

    # 先存用户消息（若有 session_id）
    if body.session_id:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM chat_sessions WHERE id = ?", (body.session_id,))
            if not cur.fetchone():
                raise HTTPException(404, "不存在的会话")
        _save_message(body.session_id, "user", body.question, [])

    # 跑 RAG 工作流
    result = RAG_GRAPH.run(body.question, top_k=top_k)
    answer = result.get("answer", "")
    refs = result.get("refs", []) or []
    model_used = result.get("model_used", "none")

    # 存 AI 消息
    if body.session_id:
        _save_message(body.session_id, "assistant", answer, refs)

    return {
        "answer": answer,
        "refs": refs,
        "model_used": model_used,
        "usage_note": result.get("usage_note", ""),
    }


# ================= SSE 流式 =================
def _stream_chars(s: str, delay_s: float = 0.01):
    """按字符 yield（无真实流时模拟），对中文友好"""
    if not s:
        return
    buf = ""
    for ch in s:
        buf += ch
        # 每 1-3 个字发一次（降低 SSE 包数）
        if len(buf) >= 2:
            yield buf
            buf = ""
            if delay_s > 0:
                time.sleep(delay_s)
    if buf:
        yield buf


async def _stream_answer(question: str, top_k: int, session_id: Optional[int]) -> AsyncIterable[str]:
    # 1) 存用户消息（同步）
    if session_id:
        try:
            with get_cursor() as cur:
                cur.execute("SELECT id FROM chat_sessions WHERE id = ?", (session_id,))
                if cur.fetchone():
                    _save_message(session_id, "user", question, [])
        except Exception:
            pass

    # 2) 检索 + 生成
    result = RAG_GRAPH.run(question, top_k=top_k)
    answer = result.get("answer", "")
    refs = result.get("refs", []) or []
    model_used = result.get("model_used", "none")
    usage_note = result.get("usage_note", "")

    # 3) 先发 meta 事件
    meta = {
        "type": "meta",
        "model_used": model_used,
        "refs": refs,
        "usage_note": usage_note,
    }
    yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

    # 4) 逐字输出（模拟 SSE）
    if config.has_any_llm_key():
        try:
            # 尝试真正的流式接口
            async for chunk in _real_stream(question, result):
                yield f"data: {json.dumps({'type':'token','content':chunk}, ensure_ascii=False)}\n\n"
        except Exception:
            for piece in _stream_chars(answer, 0.008):
                yield f"data: {json.dumps({'type':'token','content':piece}, ensure_ascii=False)}\n\n"
    else:
        # 无 Key：稍微快点输出
        for piece in _stream_chars(answer, 0.003):
            yield f"data: {json.dumps({'type':'token','content':piece}, ensure_ascii=False)}\n\n"

    # 5) 落库 AI 消息
    if session_id:
        try:
            _save_message(session_id, "assistant", answer, refs)
        except Exception:
            pass

    yield "data: [DONE]\n\n"


async def _real_stream(question: str, rag_result: dict) -> AsyncIterable[str]:
    """
    优先使用真实流式 SSE。这里做一个最小化的流式实现：
    由于 generator 类是同步非流式的，这里退化为用 httpx 直接调 stream。
    若失败则抛异常，由上层走模拟分字。
    """
    import httpx

    chunks = rag_result.get("retrieved_chunks") or []
    ref_block = []
    for i, c in enumerate(chunks, 1):
        name = c.get("doc_name") or "未知"
        ref_block.append(f"【参考{i}：{name}】\n{c.get('text') or ''}")
    context = "\n\n".join(ref_block) if ref_block else "（无参考资料）"
    prompt = (
        "根据以下参考资料回答教师提问。若参考资料不足以回答，请结合你的教学经验补充说明。\n\n"
        f"【问题】\n{question}\n\n"
        f"【参考资料】\n{context}\n\n"
        "【回答】\n"
    )
    system_prompt = "你是一位资深小学语文教师助手，回答需要具体、实用、可操作。"

    provider, endpoint, model = _provider_info_safe()
    if provider == "none":
        raise RuntimeError("no key")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
        # Token 优化：按问题长度动态调整 max_tokens（与 workflow.generate_node 一致）
        "max_tokens": 800 if len(question) < 30 else (1800 if len(question) > 100 else 1200),
    }
    if provider == "deepseek":
        key = config.get_sk_key()
    else:
        key = config.get_zhipu_key()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    collected = []
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", endpoint, headers=headers, json=body) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"stream HTTP {resp.status_code}")
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj.get("choices", [{}])[0].get("delta", {})
                        c = delta.get("content") or ""
                        if c:
                            collected.append(c)
                            yield c
                    except Exception:
                        continue
    # 如果真实流没有吐任何 token，抛异常给上层走降级
    if not collected:
        raise RuntimeError("stream empty")


def _provider_info_safe() -> tuple:
    sk = config.get_sk_key()
    if sk:
        return "deepseek", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat"
    zk = config.get_zhipu_key()
    if zk:
        return "zhipu", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "glm-4-flash"
    return "none", "", ""


@router.get("/ai/stream")
async def ai_stream_get(
    query: str = Query(..., min_length=1),
    top_k: int = Query(3, ge=1, le=20),
    session_id: Optional[int] = Query(None),
):
    return StreamingResponse(
        _stream_answer(query, top_k, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ai/stream")
async def ai_stream_post(body: AskBody):
    if not body.question or not body.question.strip():
        raise HTTPException(400, "question 不能为空")
    top_k = max(1, min(int(body.top_k or 3), 20))
    return StreamingResponse(
        _stream_answer(body.question.strip(), top_k, body.session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
