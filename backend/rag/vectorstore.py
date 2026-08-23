# -*- coding: utf-8 -*-
"""
FAISS 向量存储
- 使用 IndexFlatIP（先 L2 归一化再内积 = cosine 相似度）
- 单例 VECTOR_STORE
"""
import os
import pickle
from typing import Optional

import numpy as np

import config

# faiss 是大依赖，延迟导入以保证启动时即便没装也能启动（只在用到时抛错）
try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None


def _require_faiss():
    if faiss is None:
        raise RuntimeError("faiss-cpu 未安装，请先 pip install faiss-cpu>=1.8.0")


class FAISSVectorStore:
    def __init__(self, dim: int = config.EMBEDDING_DIM):
        _require_faiss()
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)
        self.ids: list[int] = []          # chunk id
        self.metadatas: list[dict] = []   # {doc_id, doc_name, chunk_index, category}

    # ---------- 添加 ----------
    def add(self, embeddings: np.ndarray, ids, metadatas) -> None:
        if embeddings.ndim != 2 or embeddings.shape[1] != self.dim:
            raise ValueError(f"embeddings 形状应为 (N, {self.dim})，实际 {embeddings.shape}")
        if len(ids) != len(metadatas) or len(ids) != embeddings.shape[0]:
            raise ValueError("ids/metadatas/embeddings 长度不一致")
        if len(ids) == 0:
            return
        # L2 归一化（确保 IP = cosine）
        arr = embeddings.astype(np.float32).copy()
        norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
        arr = arr / norms
        self.index.add(arr)
        self.ids.extend([int(x) for x in ids])
        self.metadatas.extend([dict(m) for m in metadatas])

    # ---------- 检索 ----------
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> list[dict]:
        """
        返回：[{chunk_id, doc_id, doc_name, text, score, chunk_index}]
        - 这里的 text 必须从 chunks 表中查询得到
        """
        if self.index.ntotal == 0:
            return []
        # 归一化 query
        q = query_embedding.astype(np.float32).reshape(1, -1)
        q_norm = np.linalg.norm(q) + 1e-9
        q = q / q_norm

        k = min(int(top_k), self.index.ntotal)
        if k <= 0:
            return []
        scores, indices = self.index.search(q, k)  # (1, k)
        out: list[dict] = []
        # 收集需要的 chunk_id → 批量查库
        wanted_chunk_ids: list[int] = []
        meta_by_idx = []
        for i in range(k):
            rank_idx = int(indices[0][i])
            if rank_idx < 0 or rank_idx >= len(self.ids):
                continue
            chunk_id = self.ids[rank_idx]
            meta = dict(self.metadatas[rank_idx]) if rank_idx < len(self.metadatas) else {}
            score = float(scores[0][i])
            wanted_chunk_ids.append(chunk_id)
            meta_by_idx.append((chunk_id, score, meta))
        # 查 chunks 表获取 text
        chunk_texts: dict[int, str] = {}
        try:
            from db import get_cursor
            if wanted_chunk_ids:
                placeholders = ",".join(["?"] * len(wanted_chunk_ids))
                with get_cursor() as cur:
                    cur.execute(
                        f"SELECT id, text FROM chunks WHERE id IN ({placeholders})",
                        wanted_chunk_ids,
                    )
                    for row in cur.fetchall():
                        chunk_texts[int(row["id"])] = row["text"]
        except Exception:
            chunk_texts = {c: "" for c in wanted_chunk_ids}
        # 组装
        for chunk_id, score, meta in meta_by_idx:
            out.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": meta.get("doc_id"),
                    "doc_name": meta.get("doc_name", ""),
                    "text": chunk_texts.get(chunk_id, ""),
                    "score": round(score, 6),
                    "chunk_index": meta.get("chunk_index"),
                }
            )
        return out

    # ---------- 持久化 ----------
    def save(self, path: str) -> None:
        _require_faiss()
        payload = {
            "ids": self.ids,
            "metadatas": self.metadatas,
            "index_bytes": faiss.serialize_index(self.index),
            "dim": self.dim,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, path: str) -> "FAISSVectorStore":
        _require_faiss()
        if not os.path.exists(path):
            return self
        with open(path, "rb") as f:
            payload = pickle.load(f)
        self.ids = list(payload.get("ids", []))
        self.metadatas = list(payload.get("metadatas", []))
        raw = payload.get("index_bytes")
        if raw is not None:
            self.index = faiss.deserialize_index(raw)
        self.dim = int(payload.get("dim", self.dim))
        return self

    @property
    def total_chunks(self) -> int:
        return len(self.ids)

    def total_docs(self) -> int:
        s = set()
        for m in self.metadatas:
            d = m.get("doc_id")
            if d is not None:
                s.add(d)
        return len(s)


# 全局单例
VECTOR_STORE: Optional[FAISSVectorStore] = None


def get_vector_store() -> FAISSVectorStore:
    global VECTOR_STORE
    if VECTOR_STORE is None:
        VECTOR_STORE = FAISSVectorStore()
        if os.path.exists(config.VECTORSTORE_PATH):
            try:
                VECTOR_STORE.load(config.VECTORSTORE_PATH)
            except Exception:
                # 损坏则新建
                VECTOR_STORE = FAISSVectorStore()
    return VECTOR_STORE


def reset_vector_store() -> FAISSVectorStore:
    """重建空向量库（用于 rebuild-kb）"""
    global VECTOR_STORE
    VECTOR_STORE = FAISSVectorStore()
    return VECTOR_STORE
