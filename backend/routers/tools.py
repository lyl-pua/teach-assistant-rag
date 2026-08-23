# -*- coding: utf-8 -*-
"""
工具调用（教案/课件/作业/论文）
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
from db import (
    get_cursor,
    rows_to_list,
    json_dumps,
    json_loads,
)

router = APIRouter(prefix="")

ALLOWED_TYPES = {"lesson_plan", "courseware", "homework", "paper"}

# Token 优化：按 tool_type 精细化 max_tokens，避免一刀切浪费
# lesson_plan 结构复杂（目标/重难点/过程/板书/反思）需较多 token
# paper 论文需最长
# courseware 课件大纲每页要点简短
# homework 分层作业相对短
TOOL_MAX_TOKENS = {
    "lesson_plan": 3000,
    "courseware": 2000,
    "homework": 1500,
    "paper": 3500,
}


class ToolGenerate(BaseModel):
    tool_type: str
    subject: str = "语文"
    grade: str = ""
    unit: str = ""
    topic: str = ""
    extra: str = ""
    top_k: int = 4


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# =========== 模板提示词 ===========
def _build_prompt_and_title(body: ToolGenerate, refs_text: str) -> tuple[str, str]:
    tool = body.tool_type
    topic = body.topic or "（请补充主题）"
    grade = body.grade or "（年级待补）"
    unit = body.unit or ""
    subject = body.subject or "语文"
    extra = body.extra or ""

    refs_block = refs_text if refs_text else "（无匹配知识库资料）"
    base_intro = (
        f"学科：{subject}，年级：{grade}，单元：{unit}，主题：{topic}。\n"
        f"教师备注：{extra}\n\n"
        f"【知识库参考】\n{refs_block}\n\n"
    )
    if tool == "lesson_plan":
        title = f"教案：{grade} {topic}"
        prompt = (
            base_intro
            + "请编写一份完整的 40-45 分钟课堂教案，使用 Markdown 输出，"
            "按以下结构：\n"
            "# 教学目标（知识与技能、过程与方法、情感态度价值观）\n"
            "# 教学重点 / 教学难点\n"
            "# 教学准备\n"
            "# 教学过程（分环节：导入、初读感知、精读探究、巩固练习、总结升华、作业布置，每环节写时间分配、教师活动、学生活动、设计意图）\n"
            "# 板书设计\n"
            "# 教学反思 / 差异化教学建议（学困生/优等生如何处理）\n"
        )
    elif tool == "courseware":
        title = f"课件大纲：{grade} {topic}"
        prompt = (
            base_intro
            + "请编写一份 PPT 课件大纲，使用 Markdown 输出，按「第 X 页 · 标题 + 要点」格式，"
            "包含：封面、目录页、单元导入（情境导入）、核心新知页面（每页 3-5 个要点）、"
            "互动练习页、总结页、作业与拓展页，共 12-18 页，每页给出教师备注。"
        )
    elif tool == "homework":
        title = f"作业设计：{grade} {topic}"
        prompt = (
            base_intro
            + "请设计分层作业（总时长控制在 20-30 分钟），使用 Markdown 输出：\n"
            "A·基础题：全体学生必做，面向双基巩固，4-6 题，附参考答案。\n"
            "B·提高题：中等以上学生选做，强调迁移应用，2-3 题，附思路提示。\n"
            "C·拓展题：学有余力选做，含跨学科/实践/探究，1-2 题。\n"
            "最后给出设计说明：每类作业对应目标、预估耗时、批改建议。"
        )
    elif tool == "paper":
        title = f"小论文提纲：{topic}"
        prompt = (
            base_intro
            + "请撰写一篇面向教学研究的小论文（约 3000 字结构），使用 Markdown 输出：\n"
            "# 摘要（研究问题/方法/结论 150-300 字）\n"
            "# 关键词 3-5 个\n"
            "# 一、引言（研究背景、问题提出、研究意义）\n"
            "# 二、相关研究/理论基础\n"
            "# 三、研究设计与方法\n"
            "# 四、主体分析（可分 2-3 小节，结合课堂案例与数据）\n"
            "# 五、结论与建议\n"
            "# 参考文献格式示例（至少 5 条）\n"
        )
    else:
        raise HTTPException(400, f"不支持的 tool_type: {tool}")
    return prompt, title


# =========== 知识库检索辅助 ===========
def _retrieve_for_tool(body: ToolGenerate):
    """返回 (chunks, refs, ref_text_block)
    Token 优化：
    1. score 阈值过滤：丢弃 score < config.RETRIEVAL_SCORE_THRESHOLD 的低相关 chunk
    2. chunk 文本截断：注入 prompt 时每个 chunk 限制 config.CHUNK_TEXT_MAX_CHARS 字符
    """
    query_parts = [body.subject, body.grade, body.unit, body.topic, body.extra]
    query = " ".join([p for p in query_parts if p]).strip() or (body.tool_type or "")
    top_k = max(1, min(int(body.top_k or 4), 10))
    chunks: list = []
    refs: list = []
    try:
        from rag.embeddings import ZhipuEmbedding
        from rag.vectorstore import get_vector_store

        embed = ZhipuEmbedding()
        qv = embed.embed_query(query)
        vs = get_vector_store()
        raw_chunks = vs.search(qv, top_k=top_k)
        # Token 优化 1：score 阈值过滤
        threshold = getattr(config, "RETRIEVAL_SCORE_THRESHOLD", 0.30)
        chunks = [c for c in raw_chunks if float(c.get("score", 0.0)) >= threshold]
        # 若全部被过滤（极端情况），保留 score 最高的 1 条作为兜底
        if not chunks and raw_chunks:
            chunks = [max(raw_chunks, key=lambda c: float(c.get("score", 0.0)))]
        for c in chunks:
            refs.append({
                "doc_name": c.get("doc_name", ""),
                "chunk_index": c.get("chunk_index"),
                "page_snippet": (c.get("text") or "")[:60].replace("\n", " "),
            })
    except Exception:
        chunks = []
        refs = []
    # 拼接 ref_text_block（Token 优化 2：每个 chunk 截断到 CHUNK_TEXT_MAX_CHARS）
    max_chars = getattr(config, "CHUNK_TEXT_MAX_CHARS", 500)
    parts = []
    for i, c in enumerate(chunks, 1):
        name = c.get("doc_name") or "未知"
        text = (c.get("text") or "")[:max_chars]
        parts.append(f"【资料{i}·{name}】\n{text}")
    ref_block = "\n\n".join(parts)
    return chunks, refs, ref_block


# =========== 模板结果（无 Key 时使用）===========
def _fallback_result(body: ToolGenerate, refs: list) -> str:
    header = (
        "⚠️ 后端未配置大模型 API Key，以下为结构化模板示例 + 检索摘要。\n"
        "请在设置页填写 DeepSeek/智谱 Key 以获得完整 AI 生成结果。\n\n"
    )
    grade = body.grade or "（年级）"
    topic = body.topic or "（主题）"
    tool = body.tool_type
    sections = []
    if tool == "lesson_plan":
        sections = [
            f"# 《{topic}》教案（{grade}）",
            "## 一、教学目标",
            "1. 知识与技能：（请结合教材要点填写）",
            "2. 过程与方法：（请结合设计意图填写）",
            "3. 情感态度价值观：（请结合主题填写）",
            "## 二、教学重点 / 难点",
            "- 重点：",
            "- 难点：",
            "## 三、教学准备：PPT、板书、教具……",
            "## 四、教学过程",
            "1. 导入（5 分钟）：情境导入",
            "2. 初读感知（10 分钟）",
            "3. 精读探究（15 分钟）",
            "4. 巩固练习（7 分钟）",
            "5. 总结升华 + 作业布置（3 分钟）",
            "## 五、板书设计",
            "## 六、教学反思 / 差异化建议",
        ]
    elif tool == "courseware":
        sections = [f"# 《{topic}》课件大纲（{grade}）"]
        titles = ["封面", "目录", "情境导入", "新知一", "新知二", "新知三",
                  "互动练习", "课堂总结", "作业布置", "封底"]
        for i, t in enumerate(titles, 1):
            sections.append(f"## 第{i}页 · {t}\n- 要点1\n- 要点2\n- 教师备注：")
    elif tool == "homework":
        sections = [
            f"# {topic} 分层作业（{grade}）",
            "## A·基础题（必做，约 15 分钟）",
            "1. ……（参考答案：……）",
            "2. ……",
            "## B·提高题（选做，约 10 分钟）",
            "1. ……（思路提示：……）",
            "## C·拓展题（选做，含实践）",
            "## 设计说明",
        ]
    elif tool == "paper":
        sections = [
            f"# 论文：《{topic}》",
            "## 摘要（150-300 字）",
            "## 关键词：",
            "## 一、引言",
            "## 二、理论基础",
            "## 三、研究方法",
            "## 四、主体分析",
            "## 五、结论与建议",
            "## 参考文献",
        ]
    result = header + "\n\n".join(sections)
    if refs:
        result += "\n\n---\n## 知识库检索摘要（{len(refs)} 条）\n"
        for i, r in enumerate(refs, 1):
            result += f"{i}. [{r.get('doc_name')}·片段{r.get('chunk_index')}] {r.get('page_snippet')}\n"
    return result


# =========== 路由 ===========
@router.get("/tools/history")
def list_tool_history(tool_type: Optional[str] = None):
    sql = "SELECT * FROM tool_runs WHERE 1=1"
    params = []
    if tool_type:
        if tool_type not in ALLOWED_TYPES:
            raise HTTPException(400, f"tool_type 必须是 {ALLOWED_TYPES}")
        sql += " AND tool_type = ?"
        params.append(tool_type)
    sql += " ORDER BY id DESC LIMIT 500"
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = rows_to_list(cur.fetchall())
    for r in rows:
        if r.get("result"):
            r["result"] = json_loads(r["result"]) or {}
    return rows


@router.post("/tools/generate")
def generate_tool(body: ToolGenerate):
    if body.tool_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"tool_type 必须是 {ALLOWED_TYPES}")

    # 1. 检索
    chunks, refs, ref_block = _retrieve_for_tool(body)

    # 2. 构造 prompt
    prompt, title = _build_prompt_and_title(body, ref_block)

    # 3. 生成 or 模板
    model_used = "none"
    if config.has_any_llm_key():
        from rag.generator import GENERATOR
        system_prompt = "你是一位资深小学语文教研员，擅长撰写教案、课件、作业、教学论文。请用 Markdown 输出结构化内容，具体、可操作。"
        # Token 优化：按 tool_type 动态调整 max_tokens
        max_tokens = TOOL_MAX_TOKENS.get(body.tool_type, 2500)
        try:
            result_text = GENERATOR.chat(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=max_tokens,
                timeout=180,
            )
            model_used = GENERATOR.current_model()
        except Exception as e:
            result_text = f"生成失败（{e}），回退模板：\n\n" + _fallback_result(body, refs)
    else:
        result_text = _fallback_result(body, refs)

    # 4. 入库
    result_payload = {
        "markdown": result_text,
        "model_used": model_used,
        "subject": body.subject,
        "grade": body.grade,
        "unit": body.unit,
        "topic": body.topic,
        "extra": body.extra,
        "refs": refs,
    }
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO tool_runs(tool_type, title, prompt, result, created_at) VALUES(?,?,?,?,?)",
            (body.tool_type, title, prompt, json_dumps(result_payload), _now()),
        )
        run_id = cur.lastrowid
    return {
        "id": run_id,
        "title": title,
        "tool_type": body.tool_type,
        "result": result_payload,
        "refs": refs,
        "model_used": model_used,
    }
