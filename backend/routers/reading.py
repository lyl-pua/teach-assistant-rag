# -*- coding: utf-8 -*-
"""
文档上传/知识库检索
"""
import os
import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

import config
from db import (
    get_cursor,
    row_to_dict,
    rows_to_list,
    json_dumps,
    json_loads,
)
from rag.parser import parse_and_chunk

router = APIRouter(prefix="")


class SearchBody(BaseModel):
    query: str
    top_k: int = 5


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _doc_with_chunks_count(doc: dict) -> dict:
    """把 meta JSON 字符串展开"""
    if doc is None:
        return None
    if doc.get("meta"):
        doc["meta"] = json_loads(doc["meta"]) or {}
    else:
        doc["meta"] = {}
    return doc


def _embed_and_add_to_vectorstore(
    doc_id: int, doc_name: str, category: str, chunk_ids: list[int], chunk_texts: list[str]
) -> int:
    """调用 embedding + 写入 vectorstore；返回实际写入数"""
    from rag.embeddings import ZhipuEmbedding
    from rag.vectorstore import get_vector_store

    if not chunk_texts:
        return 0
    embed = ZhipuEmbedding()
    vecs = embed.embed(chunk_texts)
    metadatas = [
        {
            "doc_id": doc_id,
            "doc_name": doc_name,
            "chunk_index": i,
            "category": category,
        }
        for i in range(len(chunk_ids))
    ]
    vs = get_vector_store()
    vs.add(vecs, chunk_ids, metadatas)
    try:
        vs.save(config.VECTORSTORE_PATH)
    except Exception:
        # 保存失败不报错（下一次会 rebuild）
        pass
    return len(chunk_ids)


# ---------- 列表 ----------
@router.get("/documents")
def list_documents(category: Optional[str] = None, q: Optional[str] = None):
    sql = "SELECT * FROM documents WHERE 1=1"
    params = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if q:
        sql += " AND (filename LIKE ? OR category LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])
    sql += " ORDER BY id DESC LIMIT 500"
    with get_cursor() as cur:
        cur.execute(sql, params)
        items = rows_to_list(cur.fetchall())
    return [_doc_with_chunks_count(d) for d in items]


@router.get("/documents/{doc_id}")
def get_document(doc_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "不存在的文档")
        cur.execute(
            "SELECT id, chunk_index, text, meta FROM chunks WHERE doc_id = ? ORDER BY chunk_index ASC",
            (doc_id,),
        )
        chunks = rows_to_list(cur.fetchall())
    doc = _doc_with_chunks_count(row_to_dict(row))
    doc["chunks"] = chunks
    return doc


# ---------- 上传 ----------
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(default=""),
):
    # 1. 先插入一条 documents（processing）
    filename = file.filename or "untitled.txt"
    ext = os.path.splitext(filename)[1].lower()
    allowed = {".txt", ".md", ".docx", ".pdf"}
    if ext not in allowed:
        raise HTTPException(400, f"仅支持 {allowed}，收到 {ext}")

    now = _now()
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO documents
            (filename, category, file_path, file_size, chunks_count, status, meta, created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (filename, category, "", 0, 0, "processing", "{}", now),
        )
        doc_id = int(cur.lastrowid)

    # 2. 落盘
    safe_name = f"{doc_id}_{filename.replace('/', '_').replace(chr(92), '_')}"
    save_path = os.path.join(config.DOCUMENTS_DIR, safe_name)
    try:
        content_bytes = await file.read()
        with open(save_path, "wb") as f:
            f.write(content_bytes)
        file_size = len(content_bytes)
    except Exception as e:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE documents SET status = ?, meta = ? WHERE id = ?",
                ("error", json_dumps({"error": str(e)}), doc_id),
            )
        raise HTTPException(500, f"保存文件失败: {e}")

    # 3. 解析 + 分块
    try:
        _full_text, chunks = parse_and_chunk(save_path)
    except Exception as e:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE documents SET status = ?, meta = ?, file_path = ?, file_size = ? WHERE id = ?",
                ("error", json_dumps({"error": f"parse: {e}"}), save_path, file_size, doc_id),
            )
        raise HTTPException(500, f"解析文档失败: {e}")

    # 4. 写入 chunks 表
    chunk_ids: list[int] = []
    try:
        with get_cursor(commit=True) as cur:
            for idx, text in enumerate(chunks):
                cur.execute(
                    "INSERT INTO chunks(doc_id, chunk_index, text, meta) VALUES(?,?,?,?)",
                    (doc_id, idx, text, "{}"),
                )
                chunk_ids.append(int(cur.lastrowid))
            # 先把 document 信息更新（先标 ready，若 embedding 失败也至少有 chunk 数据）
            cur.execute(
                "UPDATE documents SET file_path = ?, file_size = ?, chunks_count = ?, status = ? WHERE id = ?",
                (save_path, file_size, len(chunks), "ready", doc_id),
            )
    except Exception as e:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE documents SET status = ?, meta = ? WHERE id = ?",
                ("error", json_dumps({"error": f"chunk_db: {e}"}), doc_id),
            )
        raise HTTPException(500, f"写入分块失败: {e}")

    # 5. embedding + 写 vectorstore（允许降级为伪向量）
    try:
        _embed_and_add_to_vectorstore(doc_id, filename, category, chunk_ids, chunks)
    except Exception as e:
        # 失败只记录到 meta，不回滚文档本身
        meta = json_dumps({"embed_error": str(e)})
        with get_cursor(commit=True) as cur:
            cur.execute("UPDATE documents SET meta = ? WHERE id = ?", (meta, doc_id))

    return {"id": doc_id, "filename": filename, "chunks_count": len(chunks), "status": "ready"}


# ---------- 重新构建（单文档）----------
@router.post("/documents/{doc_id}/rebuild")
def rebuild_document(doc_id: int):
    # 查文档
    with get_cursor() as cur:
        cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "不存在的文档")
        doc = row_to_dict(row)

    file_path = doc.get("file_path") or ""
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(400, "文档文件不存在，无法重新构建")

    # 解析 + 分块
    try:
        _ft, chunks = parse_and_chunk(file_path)
    except Exception as e:
        with get_cursor(commit=True) as cur:
            cur.execute("UPDATE documents SET status='error', meta=? WHERE id=?", (
                json_dumps({"error": f"parse: {e}"}), doc_id))
        raise HTTPException(500, f"解析失败: {e}")

    # 先删除旧 chunks（级联 chunk_ids 会变）
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        chunk_ids = []
        for idx, text in enumerate(chunks):
            cur.execute(
                "INSERT INTO chunks(doc_id, chunk_index, text, meta) VALUES(?,?,?,?)",
                (doc_id, idx, text, "{}"),
            )
            chunk_ids.append(int(cur.lastrowid))
        cur.execute(
            "UPDATE documents SET chunks_count = ?, status = 'ready' WHERE id = ?",
            (len(chunks), doc_id),
        )

    # 重建整个 vectorstore 会更安全（因为删除了旧 chunk，但 vectorstore 中还留着）
    # 这里采取"全量重建"策略
    from rag.vectorstore import reset_vector_store, get_vector_store
    from rag.embeddings import ZhipuEmbedding

    vs = reset_vector_store()
    # 全部 ready 文档重新 embedding
    with get_cursor() as cur:
        cur.execute("SELECT id, filename, category FROM documents WHERE status = 'ready'")
        all_docs = rows_to_list(cur.fetchall())

    all_chunk_ids: list[int] = []
    all_chunk_texts: list[str] = []
    all_metas: list[dict] = []
    with get_cursor() as cur:
        for d in all_docs:
            cur.execute(
                "SELECT id, chunk_index, text FROM chunks WHERE doc_id = ? ORDER BY chunk_index ASC",
                (d["id"],),
            )
            rows = cur.fetchall()
            for r in rows:
                all_chunk_ids.append(int(r["id"]))
                all_chunk_texts.append(r["text"])
                all_metas.append({
                    "doc_id": d["id"],
                    "doc_name": d["filename"],
                    "chunk_index": int(r["chunk_index"]),
                    "category": d.get("category") or "",
                })
    if all_chunk_ids:
        embed = ZhipuEmbedding()
        vecs = embed.embed(all_chunk_texts)
        vs.add(vecs, all_chunk_ids, all_metas)
    try:
        vs.save(config.VECTORSTORE_PATH)
    except Exception:
        pass

    return {"rebuilt": True, "doc_chunks": len(chunks), "kb_total_chunks": vs.total_chunks}


# ---------- 删除 ----------
@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    # 取文件路径
    with get_cursor() as cur:
        cur.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "不存在的文档")
        file_path = row["file_path"]
    # 删文件
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
    # 删 DB（chunk 级联删除）
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    return {"deleted": True, "note": "向量库建议调用 /settings/rebuild-kb 清理已删除片段"}


# ---------- 知识库检索 ----------
@router.post("/knowledge/search")
def search_knowledge(body: SearchBody):
    from rag.embeddings import ZhipuEmbedding
    from rag.vectorstore import get_vector_store

    query = (body.query or "").strip()
    if not query:
        return {"query": "", "chunks": []}
    top_k = max(1, min(int(body.top_k or 5), 50))
    embed = ZhipuEmbedding()
    qv = embed.embed_query(query)
    vs = get_vector_store()
    chunks = vs.search(qv, top_k=top_k)
    return {"query": query, "top_k": top_k, "chunks": chunks}
