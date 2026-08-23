# -*- coding: utf-8 -*-
"""
RAG 工作流：使用 LangGraph StateGraph
节点：retrieve → generate
"""
from typing import TypedDict, List, Optional

import config
from rag.generator import GENERATOR  # noqa: F401

# LangGraph 导入（最小依赖）
try:
    from langgraph.graph import StateGraph, END  # type: ignore
except Exception:  # pragma: no cover
    # 若未安装，退化为顺序执行的手工 StateGraph
    class StateGraph:  # type: ignore
        def __init__(self, state_schema):
            self.state_schema = state_schema
            self.nodes = {}
            self.start_node = None
            self.edges = {}

        def add_node(self, name, fn):
            self.nodes[name] = fn

        def set_entry_point(self, name):
            self.start_node = name

        def add_edge(self, a, b):
            self.edges[a] = b

        def compile(self):
            g = self

            class _Runner:
                def invoke(self, state):
                    cur = g.start_node
                    while cur is not None and cur != "END":
                        if cur not in g.nodes:
                            break
                        state = g.nodes[cur](state)
                        nxt = g.edges.get(cur, "END")
                        if nxt == "END" or nxt is None:
                            break
                        cur = nxt
                    return state

            return _Runner()

    END = "END"


class RAGState(TypedDict, total=False):
    question: str
    top_k: int
    retrieved_chunks: List[dict]
    answer: str
    refs: List[dict]
    error: str


def _build_refs(chunks: List[dict]) -> List[dict]:
    """refs 格式：[{doc_name, chunk_index, page_snippet(前60字)}]"""
    out = []
    for c in chunks:
        text = c.get("text") or ""
        snippet = text[:60].replace("\n", " ")
        out.append(
            {
                "doc_name": c.get("doc_name", ""),
                "chunk_index": c.get("chunk_index"),
                "page_snippet": snippet,
            }
        )
    return out


def _fallback_answer(question: str, chunks: List[dict]) -> str:
    """无 Key 或 LLM 失败时，基于检索块拼接的模板回答"""
    head = "（说明：后端未配置大模型 API Key，请在设置页填写以获得智能回答。以下为知识库检索摘要）\n\n"
    if not chunks:
        return head + f"未找到与「{question}」相关的资料。"
    lines = [head + f"共检索到 {len(chunks)} 条相关资料：\n"]
    for i, c in enumerate(chunks, 1):
        name = c.get("doc_name") or "未知文档"
        idx = c.get("chunk_index") or 0
        text = (c.get("text") or "").strip()
        if len(text) > 200:
            text = text[:200] + "..."
        lines.append(f"{i}. [{name} · 片段{idx}] {text}")
    return "\n\n".join(lines)


class RAGGraph:
    def __init__(self):
        self.graph = self._build()

    def _build(self):
        graph = StateGraph(RAGState)
        graph.add_node("retrieve", self.retrieve_node)
        graph.add_node("generate", self.generate_node)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    # ---------- 节点 1：retrieve ----------
    def retrieve_node(self, state: RAGState) -> RAGState:
        from rag.embeddings import ZhipuEmbedding
        from rag.vectorstore import get_vector_store

        question = state.get("question") or ""
        top_k = int(state.get("top_k", 3) or 3)
        st = dict(state)
        try:
            embed = ZhipuEmbedding()
            qv = embed.embed_query(question)
            vs = get_vector_store()
            chunks = vs.search(qv, top_k=top_k)
            st["retrieved_chunks"] = chunks
            st["refs"] = _build_refs(chunks)
        except Exception as e:
            st["error"] = f"检索失败: {e}"
            st["retrieved_chunks"] = []
            st["refs"] = []
        return st

    # ---------- 节点 2：generate ----------
    def generate_node(self, state: RAGState) -> RAGState:
        from rag.generator import GENERATOR

        st = dict(state)
        question = st.get("question") or ""
        chunks = st.get("retrieved_chunks") or []
        st.setdefault("refs", _build_refs(chunks))

        # 无任何 LLM Key → 模板回答
        if not config.has_any_llm_key():
            st["answer"] = _fallback_answer(question, chunks)
            return st

        # 拼接 prompt
        ref_block = []
        for i, c in enumerate(chunks, 1):
            name = c.get("doc_name") or "未知"
            ref_block.append(f"【参考{i}：{name}】\n{c.get('text') or ''}")
        context = "\n\n".join(ref_block) if ref_block else "（无参考资料）"

        system_prompt = (
            "你是一位资深小学语文教师助手，回答需要具体、实用、可操作，"
            "多结合教学场景给出建议。"
        )
        prompt = (
            "根据以下参考资料回答教师提问。若参考资料不足以回答，请结合你的教学经验补充说明，"
            "并明确指出哪些内容来自经验而非资料。\n\n"
            f"【问题】\n{question}\n\n"
            f"【参考资料】\n{context}\n\n"
            "【回答】\n"
        )
        try:
            st["answer"] = GENERATOR.chat(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1500,
            )
        except Exception as e:
            st["error"] = (st.get("error") or "") + f" 生成失败: {e}"
            st["answer"] = _fallback_answer(question, chunks)
        return st

    # ---------- 入口 ----------
    def run(self, question: str, top_k: int = 3) -> dict:
        initial: RAGState = {
            "question": question,
            "top_k": int(top_k or 3),
            "retrieved_chunks": [],
            "answer": "",
            "refs": [],
            "error": "",
        }
        result = self.graph.invoke(initial)
        usage_note = ""
        if not config.has_any_llm_key():
            usage_note = "后端未配置大模型 API Key，请在设置页填写以获得智能回答。以下为知识库检索摘要。"
        elif result.get("error"):
            usage_note = f"调用过程中出现问题：{result.get('error')}"
        return {
            "question": question,
            "answer": result.get("answer", ""),
            "refs": result.get("refs", []) or [],
            "retrieved_chunks": result.get("retrieved_chunks", []) or [],
            "model_used": "none" if not config.has_any_llm_key() else GENERATOR.current_model(),
            "usage_note": usage_note,
        }


# 全局单例
RAG_GRAPH = RAGGraph()
