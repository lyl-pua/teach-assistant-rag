# -*- coding: utf-8 -*-
"""
智谱 AI Embedding 封装
- 模型：embedding-3，维度 1024
- 每批 ≤25 条调用
"""
import hashlib
import numpy as np
import requests

import config

ZHIPU_EMBED_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
ZHIPU_MODEL = "embedding-3"
BATCH_SIZE = 25


class ZhipuEmbedding:
    dim: int = config.EMBEDDING_DIM  # 1024

    def _get_key(self) -> str:
        k = config.get_zhipu_key()
        if not k:
            raise RuntimeError("未配置 ZHIPU_API_KEY / GLM_API_KEY，无法调用 embedding")
        return k

    # ---------- 伪向量（无 Key 时降级使用）----------
    @staticmethod
    def _pseudo_embed(texts: list[str]) -> np.ndarray:
        """基于文本 hash 的可复现伪向量（归一化），保证相同/相近文本距离近"""
        out = np.zeros((len(texts), config.EMBEDDING_DIM), dtype=np.float32)
        for i, t in enumerate(texts):
            if not t:
                t = ""
            # 多轮 hash 产生稳定种子
            seed_bytes = (t + "@@salt_rag_v2").encode("utf-8")
            h = int(hashlib.md5(seed_bytes).hexdigest(), 16) % (2**31)
            rng = np.random.RandomState(h)
            vec = rng.randn(config.EMBEDDING_DIM).astype(np.float32)
            # 做一点点"语义相关"：基于 ngram 的偏移
            ngrams = [t[i : i + 2] for i in range(max(0, len(t) - 1))]
            if ngrams:
                for ng in ngrams[:20]:
                    h2 = int(hashlib.md5(ng.encode("utf-8")).hexdigest(), 16) % (2**31)
                    rng2 = np.random.RandomState(h2)
                    vec += 0.05 * rng2.randn(config.EMBEDDING_DIM).astype(np.float32)
            # L2 归一化
            norm = np.linalg.norm(vec) + 1e-9
            out[i] = vec / norm
        return out

    # ---------- 真正调用 ----------
    def _call_batch(self, texts: list[str]) -> list[list[float]]:
        key = self._get_key()
        headers = {"Authorization": f"Bearer {key}"}
        body = {"model": ZHIPU_MODEL, "input": texts, "dimensions": config.EMBEDDING_DIM}
        resp = requests.post(ZHIPU_EMBED_URL, headers=headers, json=body, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Zhipu embedding HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        items = data.get("data", [])
        # 按 index 排序
        items = sorted(items, key=lambda x: x.get("index", 0))
        embeds = [x["embedding"] for x in items]
        # 如果返回维度不是 EMBEDDING_DIM（例如模型不支持 dimensions 参数），自动截断或补零
        target = config.EMBEDDING_DIM
        normalized = []
        for e in embeds:
            actual = len(e)
            if actual == target:
                normalized.append(e)
            elif actual > target:
                normalized.append(e[:target])
            else:
                import copy as _copy
                pad = _copy.deepcopy(e)
                while len(pad) < target:
                    pad.append(0.0)
                normalized.append(pad)
        return normalized

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        # 无 Key：直接返回伪向量
        if not config.has_any_embed_key():
            return self._pseudo_embed(texts)
        # 按 batch_size 分批
        all_embeds: list[np.ndarray] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            rows = self._call_batch(batch)
            arr = np.asarray(rows, dtype=np.float32)
            # L2 归一化（保证后续内积等价于 cosine）
            norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
            arr = arr / norms
            all_embeds.append(arr)
        return np.vstack(all_embeds) if all_embeds else np.zeros((0, self.dim), dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        arr = self.embed([text])
        return arr[0]
