# -*- coding: utf-8 -*-
"""
工具调用（教案/课件/作业/论文/PPT）
"""
import io
import json
import re as _re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from db import (
    get_cursor,
    rows_to_list,
    json_dumps,
    json_loads,
)

router = APIRouter(prefix="")

ALLOWED_TYPES = {"lesson_plan", "courseware", "homework", "paper", "ppt"}

# Token 优化：按 tool_type 精细化 max_tokens，避免一刀切浪费
# lesson_plan 结构复杂（目标/重难点/过程/板书/反思）需较多 token
# paper 论文需最长
# ppt 演示文稿需要输出 15-22 页 * 每页要点，长度约等于教案
TOOL_MAX_TOKENS = {
    "lesson_plan": 3000,
    "courseware": 2000,
    "homework": 1500,
    "paper": 3500,
    "ppt": 3000,
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
    elif tool == "ppt":
        title = f"PPT 演示文稿：{grade} {topic}"
        prompt = (
            base_intro
            + "你是资深语文教学 PPT 设计师。请输出 14-20 页的 Markdown‑PPT，严格按如下全部规范：\n\n"
            "【输出结构 · 每页固定格式】\n"
            "- 每一页必须以 ## 第N页 · 标题 开头（N 为页码，从 1 开始）。\n"
            "- 每页正文后都要写：> 讲师备注：……（给老师口述上课提示）。\n"
            "- 每页正文后都要写：设计意图：……（一句话说明教学思路）。\n"
            "- 每页正文末尾写：动画：[本页动画配置]（从『进入 / 强调 / 退出 / 动作路径』中选，如：玻璃卡片逐张淡入、古诗文逐行浮现、重点句呼吸闪烁、目录平滑淡入等）。\n"
            "- 禁止一页塞入整篇课文；千字长文自动拆成多页「课文原文」幻灯片。\n"
            "- 正文中的引用块符号 `>` 代表磨砂毛玻璃卡片容器，知识点、注释、提问、赏析都要用 `> 内容` 包裹，体现玻璃拟态视觉。\n\n"
            "【固定页面结构 · 语文课文精讲模板】\n"
            "1) 封面页：玻璃拟态大标题 + 副标题（学科/年级/课时）。\n"
            "2) 目录页：磨砂玻璃导航卡片（3-6 个章节）。\n"
            "3) 课程导入页：情景图文 + 引导提问（玻璃卡片）。\n"
            "4) 课文原文展示页（长文自动分页，至少 2-4 页）：双栏玻璃布局——左栏放原文，右栏放词句注释批注；每行诗句独立成行。\n"
            "5) 赏析解读页（3-5 页）：多张玻璃卡片拆解文学手法、主旨分析、结构脉络、作者背景；重点词句请使用 **加粗** 或『镂空字/边框修饰』提示。\n"
            "6) 重点字词页：字词释义玻璃卡片，标注拼音、释义、易错点。\n"
            "7) 课堂探究 / 拓展思考页：开放性提问卡片。\n"
            "8) 课堂小结页：知识汇总思维导图式要点。\n"
            "9) 作业布置页：A 基础 / B 提高 / C 拓展 分层。\n"
            "10) 结束致谢页。\n"
            "其余页数按需要在 赏析 / 互动 / 练习 之间插入，总页数控制在 14-20 之间。\n\n"
            "【视觉风格 · 玻璃拟态国风】\n"
            "- 主色调：青黛、墨蓝、茶褐、月白、朱砂点缀。\n"
            "- 背景意象：低多边形星空肌理 / 淡水墨山水 / 宣纸纹理（用文字提示即可）。\n"
            "- 字体气质：封面标题粗犷书法力量感；正文赏析雅黑；古诗文原文宋体/风雅宋；重点字镂空字、外边框修饰、色彩高亮。\n"
            "- 装饰：简约水墨线条、低多边形几何，拒绝花哨。\n\n"
            "【长文本拆分硬约束】\n"
            "- 原文每 4-6 句（或每一个完整段落）拆一页，每页附相应注释批注。\n"
            "- 重点名句自动放入独立『名句赏析』玻璃卡片。\n\n"
            "示例正文写法：\n"
            "## 第4页 · 课文原文（一）\n"
            "> 【原文左栏】\n"
            "> 庆历四年春，滕子京谪守巴陵郡。\n"
            "> 越明年，政通人和，百废具兴。\n"
            "> \n"
            "> 【注释右栏】\n"
            "> 谪：贬官。政通人和：政事顺利，百姓和乐。\n"
            "- 写作技法：开门见山，叙作记缘由。\n"
            "设计意图：先读准字音与节奏，扫清字词障碍。\n"
            "> 讲师备注：齐读一遍，点 2 名同学读单句正音。\n"
            "动画：原文逐行顺序浮现 + 注释玻璃卡片淡入。\n\n"
            "请直接输出 PPT Markdown，不需要额外开场白。"
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


# =========== PPT Markdown → 结构化 slides ===========
def _parse_ppt_slides(markdown_text: str) -> list:
    """
    将 PPT 的 Markdown 文本拆成结构化的页列表：
    [{"idx": 1, "title": "封面", "content": "...", "notes": "...", "intent": "..."}]
    """
    import re as _re
    if not markdown_text:
        return []
    slides: list = []
    # 按 "## 第N页 · 标题" 或 "## 第 N 页 · 标题" 切分
    pattern = _re.compile(r"^\s*##\s*第\s*(\d+)\s*页\s*[·\-\:：]\s*(.+?)\s*$", _re.M)
    matches = list(pattern.finditer(markdown_text))
    if not matches:
        # 兜底：按任意 H2 切
        pattern2 = _re.compile(r"^\s*##\s*(.+?)\s*$", _re.M)
        matches2 = list(pattern2.finditer(markdown_text))
        for i, m in enumerate(matches2, 1):
            start = m.end()
            end = matches2[i].start() if i < len(matches2) else len(markdown_text)
            body = markdown_text[start:end].strip(" \n\r\t-")
            slides.append(_body_to_slide(i, m.group(1).strip(), body))
        return slides
    for i, m in enumerate(matches, 1):
        idx = int(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i].start() if i < len(matches) else len(markdown_text)
        body = markdown_text[start:end].strip(" \n\r\t-")
        slides.append(_body_to_slide(idx, title, body))
    return slides


def _body_to_slide(idx, title, body: str) -> dict:
    import re as _re
    # 讲师备注（兼容中文冒号 / 多行引用块续行）
    notes_match = _re.search(
        r"(?:^|\n)\s*>?[\s　]*讲师备注[:：]?\s*([\s\S]*?)(?=\n\s*(?:[-*]|>|设计意图|动画：|动画\s*[:：]|$))",
        body, _re.M,
    )
    intent_match = _re.search(
        r"(?:^|\n)\s*设计意图[:：]\s*([\s\S]*?)(?=\n\s*(?:[-*]|>|讲师备注|动画：|动画\s*[:：]|$))",
        body, _re.M,
    )
    anim_match = _re.search(
        r"(?:^|\n)\s*动画\s*[:：]\s*\[?([^\n\]]+)\]?",
        body, _re.M,
    )
    notes = (notes_match.group(1).strip().replace("\n> ", "\n").replace("\n>", "\n")
             if notes_match else "")
    intent = (intent_match.group(1).strip() if intent_match else "")
    anim = (anim_match.group(1).strip(" 　[]\n") if anim_match else "")
    # 去除备注、设计意图、动画行
    clean = body
    for _m in [anim_match, notes_match, intent_match]:
        if _m:
            clean = clean[:_m.start()] + clean[_m.end():]
    # 移除多余空行，但保留 > 引用块行（玻璃卡片）
    cleaned_lines = []
    for ln in clean.splitlines():
        s = ln.rstrip()
        if not s.strip():
            # 最多保留一个空行
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        cleaned_lines.append(s)
    clean = "\n".join(cleaned_lines).strip("\n")
    return {
        "idx": int(idx),
        "title": title,
        "content": clean,
        "notes": notes,
        "intent": intent,
        "animation": anim,
    }


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
    elif tool == "ppt":
        sections = [f"# PPT 演示文稿：《{topic}》（{grade}）"]
        ppt_template = [
            ("封面", f"教材/学科：{subject}　年级：{grade}　单元：{unit}\n授课教师：教师姓名　日期："),
            ("目录", "1. 情境导入  2. 新知讲解  3. 互动练习  4. 总结升华  5. 作业布置"),
            ("情境导入", "设计意图：用贴近学生生活的情境或问题引入课题\n- 展示情境图 / 播放音频片段\n- 引导 2-3 名学生发言"),
            ("新知一", "设计意图：搭建基础概念\n- 要点一\n- 要点二\n- 易错点提醒\n> 讲师备注：强调板书同步"),
            ("新知二", "设计意图：深化理解，结合案例\n- 要点一\n- 要点二\n- 小组讨论 1 分钟\n> 讲师备注：点名展示"),
            ("新知三", "设计意图：联系生活/旧知\n- 要点一\n- 要点二\n- 跨学科延伸\n> 讲师备注：可播放短视频"),
            ("新知四", "设计意图：突破难点\n- 难点拆解 1\n- 难点拆解 2\n- 分层操练\n> 讲师备注：巡视学困生"),
            ("新知五", "设计意图：拓展拔高（选学）\n- 拓展要点一\n- 拓展要点二"),
            ("互动练习一", "设计意图：课堂双基巩固\n- 题 1（基础）\n- 题 2（辨析）\n- 答案与讲评"),
            ("互动练习二", "设计意图：分层应用\n- A 层：口述\n- B 层：书写\n- C 层：创编\n> 讲师备注：时间控制 3 分钟"),
            ("总结升华", "设计意图：结构化回顾 + 情感升华\n- 本课知识点串讲（3-5 条）\n- 学科素养/情感点题"),
            ("作业布置", "设计意图：对应分层作业设计\n- A 基础题（必做）\n- B 提高题（选做）\n- C 拓展实践（选做）"),
            ("板书回顾", "设计意图：呈现完整板书结构，利于课后整理笔记\n- 板书主体骨架\n- 关键公式/名句\n- 易错点标注"),
            ("封底致谢", "感谢聆听！\n敬请评委老师批评指正"),
        ]
        for i, (t, c) in enumerate(ppt_template, 1):
            sections.append(f"## 第{i}页 · {t}\n{c}")
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
    # PPT 工具：解析结构化页数组，便于前端渲染 / 转 PPTX
    ppt_slides = []
    if body.tool_type == "ppt":
        try:
            ppt_slides = _parse_ppt_slides(result_text)
            result_payload["ppt_slides"] = ppt_slides
        except Exception:
            ppt_slides = []
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
        **({"ppt_slides": ppt_slides} if ppt_slides else {}),
    }


# =========== PPT 导出为 .pptx（python-pptx 16:9）===========
def _safe_filename(s: str, default: str = "教学演示文稿") -> str:
    s = (s or default).strip()
    s = _re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s)
    s = s.strip(" ._")
    return s[:80] or default


def _markdown_to_plain_lines(md: str, max_bullets: int = 6):
    """把每页 markdown 主体拆成适合 PPT 的要点行。返回 (lines, has_bullets)。"""
    if not md:
        return [], False
    out = []
    had_bullet = False
    for ln in str(md).splitlines():
        ln = ln.rstrip()
        if not ln.strip():
            continue
        # 去掉 markdown heading
        m = _re.match(r"^\s*#{1,6}\s*(.*)$", ln)
        if m:
            out.append(("title", m.group(1).strip()))
            continue
        # 引用
        if ln.lstrip().startswith(">"):
            out.append(("quote", ln.lstrip()[1:].strip()))
            continue
        # 列表
        m2 = _re.match(r"^\s*(?:[-*]|\d+\.)\s+(.*)$", ln)
        if m2:
            had_bullet = True
            out.append(("bullet", m2.group(1).strip()))
            continue
        out.append(("para", ln.strip()))
    # 限制要点数（避免一页塞太满）
    if max_bullets and len(out) > max_bullets:
        out = out[:max_bullets]
    return out, had_bullet


def _render_markdown_into_tf(tf, text: str):
    """按最小 Markdown（**粗体**、`code`）渲染到 python-pptx TextFrame。"""
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    text = text or ""
    # 把 **xxx** 替换成占位符，保证按段换行
    lines = text.split("\n") if text else [""]
    first_paragraph_done = False
    for ln in lines:
        if first_paragraph_done:
            p = tf.add_paragraph()
        else:
            p = tf.paragraphs[0]
            first_paragraph_done = True
        # 解析 **bold** 与 `code`：以正则分段
        tokens = []
        pattern = _re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")
        last = 0
        for mt in pattern.finditer(ln):
            if mt.start() > last:
                tokens.append(("plain", ln[last:mt.start()]))
            span = mt.group(0)
            if span.startswith("`"):
                tokens.append(("code", span[1:-1]))
            else:
                tokens.append(("bold", span[2:-2]))
            last = mt.end()
        if last < len(ln):
            tokens.append(("plain", ln[last:]))
        if not tokens:
            tokens = [("plain", ln)]
        first_run_done = False
        for kind, t in tokens:
            if first_run_done:
                run = p.add_run()
            else:
                if p.runs:
                    run = p.runs[0]
                    run.text = t
                else:
                    run = p.add_run()
                    run.text = t
                first_run_done = True
                continue
            run.text = t
            if kind == "bold":
                run.font.bold = True
                run.font.color.rgb = None  # 继承主题色
            elif kind == "code":
                try:
                    from pptx.dml.color import RGBColor
                    run.font.color.rgb = RGBColor(0x5A, 0x3F, 0x22)
                except Exception:
                    pass
                run.font.italic = True
    return tf


def _build_pptx_file_bytes(title: str, slides: list, theme_info: dict = None) -> bytes:
    """把结构化 slides 生成 .pptx 文件（16:9，国风+玻璃拟态配色：青黛/墨蓝/茶褐/月白）。
    本版新增：每页写入原生 <p:transition> 切换动画（浮现/揭开/擦除等）+ <p:timing> 段落逐条浮现入场。
    PowerPoint/WPS 全屏放映即有动态效果。
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        from lxml import etree
    except Exception as e:
        raise HTTPException(500, f"服务器未安装 python-pptx / lxml，请管理员执行 pip install python-pptx lxml：{e}")

    # ========= OOXML 命名空间常量 =========
    NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
    NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    P = f"{{{NS_P}}}"
    A = f"{{{NS_A}}}"
    QN_P = lambda tag: f"{NS_P}:{tag}"  # noqa: E731
    QN_A = lambda tag: f"{NS_A}:{tag}"  # noqa: E731

    theme_info = theme_info or {}
    subject = theme_info.get("subject") or "语文"
    grade = theme_info.get("grade") or ""
    teacher = theme_info.get("teacher") or "主讲教师"

    prs = Presentation()
    # 16:9
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    SW, SH = prs.slide_width, prs.slide_height
    blank_layout = prs.slide_layouts[6]  # 空白版式

    # ========= 动画：页面切换 + 对象入场 =========
    TRANSITION_PRESETS = {
        # 浮现（fade）——用户"浮现"核心诉求
        "fade": lambda: etree.fromstring(
            f'<p:transition xmlns:p="{NS_P}"><p:fade/></p:transition>'
        ),
        # 推挤（自下向上推进）——"揭开"体感 1
        "push": lambda: etree.fromstring(
            f'<p:transition xmlns:p="{NS_P}"><p:push dir="u"/></p:transition>'
        ),
        # 擦除 / 拉开（自左向右揭开）——"揭开"体感 2（最常用）
        "wipe": lambda: etree.fromstring(
            f'<p:transition xmlns:p="{NS_P}"><p:wipe dir="r"/></p:transition>'
        ),
        # 覆盖（自左向右覆盖）——"揭开"变体
        "cover": lambda: etree.fromstring(
            f'<p:transition xmlns:p="{NS_P}"><p:cover dir="r"/></p:transition>'
        ),
        # 分割（水平向外对开）——"揭开"变体
        "split": lambda: etree.fromstring(
            f'<p:transition xmlns:p="{NS_P}"><p:split orient="horz" dir="out"/></p:transition>'
        ),
        # 溶解 dissolve —— 强浮现/渐隐渐显
        "dissolve": lambda: etree.fromstring(
            f'<p:transition xmlns:p="{NS_P}"><p:dissolve/></p:transition>'
        ),
    }

    # PPT 数据 slides[i].animation 字段 → (切换类型, 入场段落模式)
    def _resolve_anim_preset(anim_text: str, is_cover: bool, is_end: bool, is_toc: bool, idx: int):
        t = (anim_text or "").strip()
        # 用户强需求关键字优先
        if any(k in t for k in ("浮现", "淡入", "渐现", "渐显", "fade", "appear")):
            return ("fade", "by_para_fade")
        if any(k in t for k in ("揭开", "掀开", "展开", "拉开", "wipe", "uncover")):
            return ("wipe", "by_para_fade")
        if any(k in t for k in ("推挤", "推进", "推入", "push")):
            return ("push", "by_para_fade")
        if any(k in t for k in ("覆盖", "cover")):
            return ("cover", "by_para_fade")
        if any(k in t for k in ("溶解", "融", "dissolve")):
            return ("dissolve", "by_para_fade")
        if any(k in t for k in ("分割", "split", "对开")):
            return ("split", "by_para_fade")
        if any(k in t for k in ("呼吸", "强调", "缩放", "zoom")):
            # 用 fade 切换 + 入场多一点延迟，体感"呼吸浮现"
            return ("fade", "by_para_fade_slow")
        if any(k in t for k in ("逐行", "逐条", "逐个", "顺序")):
            return ("fade", "by_para_fade")
        # 页面语义默认
        if is_cover:  return ("fade",     "all_together_fade")   # 封面：整体浮现
        if is_toc:    return ("wipe",     "by_para_fade")        # 目录：逐条揭开
        if is_end:    return ("dissolve", "all_together_fade")   # 封底：整体溶解
        # 正文页交替：奇=浮现 偶=揭开
        return (("fade" if idx % 2 == 1 else "wipe"), "by_para_fade")

    def _apply_slide_transition(slide, kind="fade", dur_ms: int = 650):
        """把 <p:transition> 写入 slide._element（p:sld）。
        OOXML 标准顺序：p:cSld -> p:clrMapOvr -> p:transition -> p:timing -> p:extLst
        必须保证插入在 <p:clrMapOvr> 之后；否则 XML 非法会被下游解析器静默丢弃。
        """
        maker = TRANSITION_PRESETS.get(kind) or TRANSITION_PRESETS["fade"]
        try:
            # 先移除旧 transition 避免重复
            for old in list(slide._element.findall(P + "transition")):
                slide._element.remove(old)
            trans = maker()
            # 查找 clrMapOvr 位置，transition 放其后
            clr = slide._element.find(P + "clrMapOvr")
            if clr is not None:
                idx_clr = list(slide._element).index(clr)
                slide._element.insert(idx_clr + 1, trans)
            else:
                # 没找到 clrMapOvr（理论不会有），放末尾
                slide._element.append(trans)
        except Exception:
            pass

    def _apply_entry_animations(slide, mode="by_para_fade"):
        """把 <p:timing> 段落入场浮现动画写入 slide._element。
        位置：<p:transition> 之后（OOXML 要求 transition 先，timing 后）。
        """
        try:
            shapes = list(slide.shapes)
            if not shapes:
                return
            cTn_paras = []
            delay_acc_ms = 0
            dur_para = 500 if mode == "by_para_fade_slow" else 350
            step_delay = 180 if mode == "by_para_fade_slow" else 120
            for sp in shapes:
                # 取 spId：统一用 cNvPr/@id
                cNvPr = sp._element.find(".//" + P + "cNvPr")
                if cNvPr is None:
                    cNvPr = sp._element.find(".//" + A + "cNvPr")
                if cNvPr is None:
                    continue
                sp_id = cNvPr.get("id")
                if not sp_id:
                    continue

                # 取该 shape 的段落数
                txBody = sp._element.find(".//" + P + "txBody")
                if txBody is None:
                    txBody = sp._element.find(".//" + A + "txBody")
                paras_count = 1
                if txBody is not None:
                    paras_count = max(1, len(txBody.findall(A + "p")))

                if mode == "all_together_fade":
                    # 整体
                    para_delay = delay_acc_ms
                    delay_acc_ms += 250
                    cTn_paras.append(_fade_par_xml(
                        sp_id, idx=None, delay_ms=para_delay, dur_ms=600
                    ))
                else:
                    # 逐条
                    for pi in range(paras_count):
                        para_delay = delay_acc_ms
                        delay_acc_ms += step_delay
                        cTn_paras.append(_fade_par_xml(
                            sp_id, idx=pi, delay_ms=para_delay, dur_ms=dur_para
                        ))
            if not cTn_paras:
                return
            # 移除旧 timing
            for old in list(slide._element.findall(P + "timing")):
                slide._element.remove(old)
            # 保证 transition 先有（即便默认 fade，也确保 timing 有前序元素）
            if slide._element.find(P + "transition") is None:
                _apply_slide_transition(slide, "fade", 500)
            # 组装 timing
            timing_xml = (
                f'<p:timing xmlns:p="{NS_P}" xmlns:a="{NS_A}">'
                f'<p:tnLst><p:par>'
                f'<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
                f'<p:childTnLst>'
                f'{"".join(cTn_paras)}'
                f'</p:childTnLst>'
                f'</p:cTn>'
                f'</p:par></p:tnLst>'
                f'<p:bldLst/>'
                f'</p:timing>'
            )
            timing_el = etree.fromstring(timing_xml)
            # 插入位置：必须在 <p:transition> 之后
            trans_el = slide._element.find(P + "transition")
            if trans_el is not None:
                idx_trans = list(slide._element).index(trans_el)
                slide._element.insert(idx_trans + 1, timing_el)
            else:
                slide._element.append(timing_el)
        except Exception:
            # 动画：渐进增强，失败不影响内容
            pass

    def _fade_par_xml(sp_id, idx=None, delay_ms=0, dur_ms=400):
        """为单段落/单 shape 生成一条 <p:par>(Fade 浮现入场)。
        idx=None -> 整体对象（shape）；idx=int -> 按段落索引（bldLvl）。
        用 p:set 显示 + a:fade 效果组合的最简兼容 Fade。
        """
        condDelay = f'<p:cond delay="{delay_ms}"/>'
        # 1) 显示：p:set -> objectR/TgtEl/txEl
        tgt = ""
        if idx is None:
            tgt = (
                f'<p:tgtEl><p:spTgt spid="{sp_id}"/></p:tgtEl>'
            )
        else:
            tgt = (
                f'<p:tgtEl><p:spTgt spid="{sp_id}">'
                f'<p:txEl><p:pRg st="{idx}" end="{idx}"/></p:txEl>'
                f'</p:spTgt></p:tgtEl>'
            )
        # cTn id 必须全局递增；这里直接用 hash 组合防重（只要不与同页兄弟冲突即可）
        import hashlib
        seed = f"{sp_id}-{idx}-{delay_ms}-{dur_ms}"
        ctn_id1 = abs(int(hashlib.md5(seed.encode()).hexdigest()[:6], 16)) % 2100000000 + 1000
        ctn_id2 = ctn_id1 + 1
        ctn_id3 = ctn_id2 + 1
        ctn_id4 = ctn_id3 + 1
        ctn_id5 = ctn_id4 + 1
        # 构建：<p:par condLst> 延迟 -> <p:seq concurrent="1" nextAc="seek"> 不可用；最稳：<p:par> 包 cTn+effect
        # 使用 Fade 动画：p:animEffect transition="in" filter="fade"
        xml = (
            f'<p:par xmlns:p="{NS_P}" xmlns:a="{NS_A}">'
            f'<p:cTn id="{ctn_id1}" dur="indefinite" fill="hold">'
            f'<p:stCondLst>{condDelay}</p:stCondLst>'
            f'<p:childTnLst>'
            # 子 par1: 显示 (visibility set)
            f'<p:par>'
            f'<p:cTn id="{ctn_id2}" dur="1" fill="hold">'
            f'<p:childTnLst>'
            f'<p:set>'
            f'<p:cBhvr>'
            f'{tgt}'
            f'<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>'
            f'</p:cBhvr>'
            f'<p:to><p:strVal val="visible"/></p:to>'
            f'</p:set>'
            f'</p:childTnLst>'
            f'</p:cTn>'
            f'</p:par>'
            # 子 par2: Fade 浮现入场
            f'<p:par>'
            f'<p:cTn id="{ctn_id3}" dur="{dur_ms}" fill="hold">'
            f'<p:childTnLst>'
            f'<p:animEffect transition="in" filter="fade">'
            f'<p:cBhvr additive="base" override="childStyle">'
            f'{tgt}'
            f'</p:cBhvr>'
            f'</p:animEffect>'
            f'</p:childTnLst>'
            f'</p:cTn>'
            f'</p:par>'
            f'</p:childTnLst>'
            f'</p:cTn>'
            f'</p:par>'
        )
        return xml

    # ===== 玻璃拟态国风 4 色板 =====
    # 青黛、墨蓝、茶褐、月白；朱砂点缀；米白辅助
    C_QINGDAI   = RGBColor(0x2A, 0x50, 0x47)  # 主绿
    C_MOLAN     = RGBColor(0x1F, 0x3A, 0x5A)  # 墨蓝
    C_CHAHE     = RGBColor(0x5A, 0x3F, 0x22)  # 茶褐
    C_ZHUSHA    = RGBColor(0x83, 0x3F, 0x21)  # 朱砂（印章/强调）
    C_YUEBAI    = RGBColor(0xF7, 0xF2, 0xE3)  # 月白（底色）
    C_MIBAI     = RGBColor(0xFF, 0xFC, 0xF4)  # 米白
    C_GOLD      = RGBColor(0xC8, 0xA0, 0x6B)  # 金色分隔
    C_ACCENT    = RGBColor(0xA5, 0x6A, 0x3B)  # 赭石（辅助）
    C_DARK_BG   = RGBColor(0x14, 0x26, 0x32)  # 封面底（墨蓝深）
    C_DARK_BG_2 = RGBColor(0x2A, 0x50, 0x47)  # 封面底 2（青黛）
    C_TEXT_DARK = RGBColor(0x2A, 0x32, 0x38)  # 正文深灰
    C_GLASS_A   = RGBColor(0xFB, 0xF7, 0xEB)  # 玻璃卡片半透浅
    C_GLASS_B   = RGBColor(0xF2, 0xEA, 0xD6)  # 玻璃卡片次

    # 字体（兼容 Windows / macOS / Linux 常见字体）
    FONT_TITLE   = "STFangsong"   # 标题：仿宋（书法感）/ FangSong
    FONT_BODY    = "Microsoft YaHei"  # 正文雅黑
    FONT_GUWEN   = "SimSun"       # 古诗文原文宋体（风雅宋备选）
    FONT_KAITI   = "STKaiti"      # 楷体：注释
    FONT_HEITI   = "SimHei"       # 黑体兜底

    def _set_run_font(run, name=FONT_BODY, size=None, bold=None, italic=None, color=None):
        if name:
            try:
                run.font.name = name
                from lxml import etree
                rPr = run._r.get_or_add_rPr()
                ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
                # Latin + EastAsia
                for tag, v in [("latin", name), ("ea", name)]:
                    el = rPr.find(ns + tag)
                    if el is None:
                        el = etree.SubElement(rPr, ns + tag)
                    el.set("typeface", v)
            except Exception:
                pass
        if size is not None:
            try: run.font.size = Pt(size)
            except Exception: pass
        if bold is not None:
            try: run.font.bold = bool(bold)
            except Exception: pass
        if italic is not None:
            try: run.font.italic = bool(italic)
            except Exception: pass
        if color is not None:
            try: run.font.color.rgb = color
            except Exception: pass

    def _bg(slide, color):
        try:
            bg = slide.background
            fill = bg.fill
            from pptx.enum.dml import MSO_FILL
            fill.solid()
            fill.fore_color.rgb = color
        except Exception:
            pass

    def _rounded_rect(slide, x, y, w, h, fill_color=None, line_color=None, line_w=None, radius="small"):
        """玻璃圆角矩形（磨砂卡片）。"""
        from pptx.enum.shapes import MSO_SHAPE
        shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
        shp = slide.shapes.add_shape(shape_type, x, y, w, h)
        # 调整圆角半径
        try:
            if radius == "big":
                shp.adjustments[0] = 0.15
            elif radius == "small":
                shp.adjustments[0] = 0.08
            else:
                shp.adjustments[0] = 0.04
        except Exception:
            pass
        if fill_color is None:
            try: shp.fill.background()
            except Exception: shp.fill.solid(); shp.fill.fore_color.rgb = RGBColor(0xFF,0xFF,0xFF)
        else:
            shp.fill.solid()
            shp.fill.fore_color.rgb = fill_color
            try:
                # 透明度：用 XML 注入 alpha（半透明玻璃感）
                from lxml import etree
                solid = shp.fill._fill
                ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
                srgb = solid.find(ns + "solidFill")
                if srgb is not None:
                    alpha = srgb.find(ns + "alpha")
                    if alpha is None:
                        alpha = etree.SubElement(srgb, ns + "alpha")
                    alpha.set("val", "82000")  # ~50% 透明
            except Exception:
                pass
        if line_color is None:
            try: shp.line.fill.background()
            except Exception: pass
        else:
            try:
                shp.line.color.rgb = line_color
                if line_w is not None:
                    shp.line.width = line_w
            except Exception:
                pass
        try: shp.shadow.inherit = False
        except Exception: pass
        return shp

    def _rect(slide, x, y, w, h, fill_color=None, line_color=None, line_w=None):
        from pptx.enum.shapes import MSO_SHAPE
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
        if fill_color is None:
            shape.fill.background()
        else:
            shape.fill.solid()
            shape.fill.fore_color.rgb = fill_color
        if line_color is None:
            try: shape.line.fill.background()
            except Exception: pass
        else:
            try:
                shape.line.color.rgb = line_color
                if line_w is not None: shape.line.width = line_w
            except Exception: pass
        try: shape.shadow.inherit = False
        except Exception: pass
        return shape

    def _textbox(slide, x, y, w, h, text="", *, size=18, bold=False, color=None,
                 align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font_name=FONT_BODY, italic=False):
        tb = slide.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.10)
        tf.margin_right = Inches(0.10)
        tf.margin_top = Inches(0.05)
        tf.margin_bottom = Inches(0.05)
        tf.vertical_anchor = anchor
        p = tf.paragraphs[0]
        p.alignment = align
        r = p.add_run()
        r.text = text or ""
        _set_run_font(r, font_name, size, bold, italic, color)
        return tb

    def _add_slide_notes(slide, notes_text: str, intent_text: str = "", animation_text: str = "",
                         trans_kind: str = "fade", entry_mode: str = "by_para_fade"):
        """写入 PPT 原生 notes 页（放映者模式），并写入页面切换+对象入场 OOXML 动画。
        注意：此函数是逐页写入动画的**唯一出口**——所有分支（封面/目录/正文/封底）在 continue
        或进入下一页之前都调用它，因此把 transition + timing 收口在这里避免漏写。
        """
        # ① 写 notes
        if notes_text or intent_text or animation_text:
            try:
                notes_slide = slide.notes_slide
                tf = notes_slide.notes_text_frame
                parts = []
                if intent_text:
                    parts.append("【设计意图】" + intent_text.strip())
                if animation_text:
                    parts.append("【动画】" + animation_text.strip())
                if notes_text:
                    parts.append("【讲师备注】" + notes_text.strip())
                tf.text = "\n\n".join(parts)
            except Exception:
                pass
        # ② 写原生 PPT 动画（切换 + 入场）—— 渐进增强，失败不影响内容
        _apply_slide_transition(slide, trans_kind, dur_ms=650)
        _apply_entry_animations(slide, mode=entry_mode)

    def _poly_decor(slide):
        """低多边形装饰（左上/右下散点）。"""
        from pptx.enum.shapes import MSO_SHAPE
        try:
            for cx, cy, sz, col in [
                (Inches(0.25), Inches(0.3), Inches(0.16), C_QINGDAI),
                (Inches(0.55), Inches(0.2), Inches(0.09), C_ACCENT),
                (Inches(12.6), Inches(7.05), Inches(0.18), C_ZHUSHA),
                (Inches(12.9), Inches(6.75), Inches(0.10), C_CHAHE),
                (Inches(12.3), Inches(7.22), Inches(0.07), C_QINGDAI),
            ]:
                s = slide.shapes.add_shape(MSO_SHAPE.OVAL, cx, cy, sz, sz)
                s.fill.solid(); s.fill.fore_color.rgb = col
                try: s.line.fill.background(); s.shadow.inherit = False
                except Exception: pass
        except Exception:
            pass

    def _slide_page_decor(slide, page_no=None, anim_text=None):
        """每页装饰：顶部装饰线 + 页码 + 学科角标 + 动画标记小胶囊。"""
        # 顶部 双线装饰：茶褐细线 + 青黛主条
        _rect(slide, Inches(0.6), Inches(0.48), Inches(12.133), Emu(6350),  # 0.067"
              fill_color=C_ACCENT)
        _rect(slide, Inches(0.6), Inches(0.60), Inches(12.133), Emu(19050),  # 0.2"
              fill_color=C_QINGDAI, line_color=None)
        # 右上角印章
        from pptx.enum.shapes import MSO_SHAPE
        try:
            stamp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(12.5), Inches(0.75), Inches(0.5), Inches(0.5))
            stamp.fill.solid(); stamp.fill.fore_color.rgb = C_ZHUSHA
            try: stamp.line.color.rgb = C_ZHUSHA; stamp.shadow.inherit = False
            except Exception: pass
            stb = slide.shapes.add_textbox(Inches(12.51), Inches(0.78), Inches(0.48), Inches(0.46))
            stf = stb.text_frame
            stf.margin_left = stf.margin_right = Emu(0)
            stf.margin_top = stf.margin_bottom = Emu(0)
            pp = stf.paragraphs[0]
            pp.alignment = PP_ALIGN.CENTER
            rr = pp.add_run(); rr.text = "教"
            _set_run_font(rr, FONT_KAITI, 26, True, False, C_YUEBAI)
        except Exception:
            pass
        # 右下角 页码
        if page_no is not None:
            _textbox(slide, Inches(12.15), Inches(7.02), Inches(1.1), Inches(0.32),
                     f"— {page_no} —",
                     size=11, color=C_ACCENT, align=PP_ALIGN.RIGHT, italic=True, font_name=FONT_TITLE)
        # 学科年级 角标（左上）
        tag = f"{grade} · {subject}" if grade else subject
        if tag:
            _textbox(slide, Inches(0.6), Inches(0.10), Inches(6), Inches(0.30),
                     tag, size=11, color=C_ACCENT, italic=True, font_name=FONT_TITLE)
        # 动画标记（玻璃胶囊，右下偏上）
        if anim_text:
            anim_short = anim_text if len(anim_text) < 26 else anim_text[:24] + "…"
            cap = _rounded_rect(slide, Inches(9.8), Inches(7.00), Inches(2.3), Inches(0.34),
                                fill_color=C_GLASS_A, line_color=C_GOLD, line_w=Pt(0.75), radius="small")
            _textbox(slide, Inches(9.82), Inches(7.01), Inches(2.26), Inches(0.32),
                     "✨ " + anim_short, size=10, bold=False, color=C_CHAHE,
                     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_KAITI, italic=True)
        _poly_decor(slide)

    def _glass_card(slide, x, y, w, h, accent=None, radius="small"):
        """绘制一张磨砂玻璃卡片（白描边 + 半透明底 + 淡阴影）。"""
        from pptx.enum.shapes import MSO_SHAPE
        accent = accent or C_QINGDAI
        # 底部淡阴影
        try:
            shadow_bg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                               x + Inches(0.06), y + Inches(0.09), w, h)
            shadow_bg.fill.solid(); shadow_bg.fill.fore_color.rgb = C_TEXT_DARK
            try: shadow_bg.fill.fore_color.brightness = 0.6
            except Exception: pass
            try:
                from lxml import etree
                ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
                sf = shadow_bg.fill._fill.find(ns + "solidFill")
                if sf is not None:
                    alpha = sf.find(ns + "alpha")
                    if alpha is None:
                        from lxml import etree as _et
                        alpha = _et.SubElement(sf, ns + "alpha")
                    alpha.set("val", "12000")  # ~7% 深色投影
            except Exception:
                pass
            try: shadow_bg.line.fill.background(); shadow_bg.shadow.inherit = False
            except Exception: pass
            # 把阴影挪到最底层
            try:
                spTree = slide.shapes._spTree
                spTree.remove(shadow_bg._element)
                spTree.insert(2, shadow_bg._element)
            except Exception:
                pass
        except Exception:
            pass
        card = _rounded_rect(slide, x, y, w, h, fill_color=C_GLASS_A,
                             line_color=RGBColor(0xFF,0xFF,0xFF), line_w=Pt(1.25), radius=radius)
        # 左侧细边（accent 色）
        try:
            strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x + Emu(3810), y + Inches(0.08),
                                           Inches(0.06), h - Inches(0.16))
            strip.fill.solid(); strip.fill.fore_color.rgb = accent
            try: strip.line.fill.background(); strip.shadow.inherit = False
            except Exception: pass
        except Exception:
            pass
        return card

    # ---------- 逐页渲染 ----------
    if not slides:
        slides = [{"idx": 1, "title": title or "演示文稿", "content": "", "notes": "", "intent": "", "animation": ""}]

    PALETTE_CYCLE = [C_QINGDAI, C_ZHUSHA, C_CHAHE, C_MOLAN, C_ACCENT, C_GOLD]

    for i, raw in enumerate(slides, 1):
        slide = prs.slides.add_slide(blank_layout)
        _bg(slide, C_MIBAI)
        idx = int(raw.get("idx") or i)
        s_title = raw.get("title") or "未命名"
        s_content = raw.get("content") or ""
        s_notes = raw.get("notes") or ""
        s_intent = raw.get("intent") or ""
        s_anim = raw.get("animation") or ""
        is_cover = (i == 1) or ("封面" in s_title)
        is_toc = (i == 2) or ("目录" in s_title)
        is_end = (i == len(slides)) or ("封底" in s_title or "致谢" in s_title)
        # ====== 动画预设：根据 slides[i].animation 字段 + 页面语义推导 ======
        trans_kind, entry_mode = _resolve_anim_preset(s_anim, is_cover, is_end, is_toc, i)

        if is_cover:
            # 封面：墨深蓝 → 青黛对角渐变底 + 玻璃标题卡
            _bg(slide, C_DARK_BG)
            # 对角装饰色块
            _rect(slide, Inches(0), Inches(0), Inches(0.38), SH, fill_color=C_ZHUSHA)
            _rect(slide, Inches(0.48), Inches(0), Inches(0.10), SH, fill_color=C_MOLAN)
            # 左上多边形装饰
            _poly_decor(slide)
            # 大标题玻璃卡片
            _glass_card(slide, Inches(1.9), Inches(1.8), Inches(10.6), Inches(2.2), accent=C_GOLD, radius="big")
            tb_title = _textbox(slide, Inches(2.1), Inches(2.0), Inches(10.2), Inches(1.8),
                                title or s_title, size=52, bold=True, color=C_CHAHE,
                                align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_TITLE)
            # 主标题下 金色分隔
            _rect(slide, Inches(2.1), Inches(4.05), Inches(3.0), Emu(25400), fill_color=C_GOLD)
            # 副标题玻璃卡
            sub_parts = []
            if grade: sub_parts.append(f"年级：{grade}")
            if subject: sub_parts.append(f"学科：{subject}")
            actual_ttl = s_title if (title and s_title != title) else "——"
            sub_parts.append(f"课题：{actual_ttl}")
            _glass_card(slide, Inches(2.1), Inches(4.25), Inches(8.0), Inches(1.3), accent=C_QINGDAI, radius="small")
            _textbox(slide, Inches(2.3), Inches(4.35), Inches(7.6), Inches(1.1),
                     "\n".join(sub_parts), size=18, color=C_TEXT_DARK,
                     align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, italic=True, font_name=FONT_KAITI)
            # 主讲人 / 日期
            _textbox(slide, Inches(2.1), Inches(5.85), Inches(8), Inches(0.4),
                     f"主讲人：{teacher}", size=14, color=C_GOLD, align=PP_ALIGN.LEFT, font_name=FONT_BODY)
            _textbox(slide, Inches(2.1), Inches(6.30), Inches(8), Inches(0.4),
                     datetime.now().strftime("%Y 年 %m 月"),
                     size=12, color=C_MIBAI, italic=True, align=PP_ALIGN.LEFT, font_name=FONT_KAITI)
            # 左下圆印章
            from pptx.enum.shapes import MSO_SHAPE
            try:
                seal = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(10.9), Inches(5.85), Inches(1.55), Inches(1.55))
                seal.fill.solid(); seal.fill.fore_color.rgb = C_ZHUSHA
                try: seal.line.color.rgb = C_ZHUSHA; seal.shadow.inherit = False
                except Exception: pass
                stb = slide.shapes.add_textbox(Inches(10.92), Inches(6.18), Inches(1.5), Inches(1.0))
                stf = stb.text_frame; stf.word_wrap = True; stf.vertical_anchor = MSO_ANCHOR.MIDDLE
                pp = stf.paragraphs[0]; pp.alignment = PP_ALIGN.CENTER
                rr = pp.add_run(); rr.text = "国风\n教研"
                _set_run_font(rr, FONT_KAITI, 26, True, False, C_YUEBAI)
            except Exception:
                pass
            # notes + 动画（动画收口在 _add_slide_notes 内）
            _add_slide_notes(slide, s_notes, s_intent, s_anim, trans_kind, entry_mode)
            continue

        if is_end:
            # 封底：青黛深底
            _bg(slide, C_DARK_BG_2)
            _rect(slide, Inches(0), Inches(0), Inches(0.38), SH, fill_color=C_ZHUSHA)
            _poly_decor(slide)
            _glass_card(slide, Inches(1.8), Inches(2.8), Inches(9.7), Inches(2.4), accent=C_GOLD, radius="big")
            _textbox(slide, Inches(0), Inches(3.10), SW, Inches(1.2),
                     s_title or "感谢聆听！", size=50, bold=True, color=C_CHAHE,
                     align=PP_ALIGN.CENTER, font_name=FONT_TITLE)
            _rect(slide, Inches(6.0), Inches(4.40), Inches(1.333), Emu(25400), fill_color=C_GOLD)
            _textbox(slide, Inches(0), Inches(4.65), SW, Inches(0.45),
                     (f"{subject} · {grade}" if grade else subject),
                     size=15, color=C_DARK_BG, align=PP_ALIGN.CENTER, italic=True, font_name=FONT_KAITI)
            _textbox(slide, Inches(0), Inches(5.25), SW, Inches(0.4),
                     "欢迎批评指正", size=14, color=C_MOLAN,
                     align=PP_ALIGN.CENTER, italic=True, font_name=FONT_KAITI)
            _add_slide_notes(slide, s_notes, s_intent, s_anim, trans_kind, entry_mode)
            continue

        if is_toc:
            # 目录页：左侧 青黛玻璃大卡 写『目录』；右侧条目卡片
            _slide_page_decor(slide, idx, s_anim)
            # 左
            _glass_card(slide, Inches(0.6), Inches(1.0), Inches(3.4), Inches(5.7), accent=C_QINGDAI, radius="big")
            _textbox(slide, Inches(0.85), Inches(1.55), Inches(2.9), Inches(2.0),
                     "目  录", size=48, bold=True, color=C_QINGDAI,
                     align=PP_ALIGN.CENTER, font_name=FONT_TITLE)
            _textbox(slide, Inches(0.85), Inches(3.8), Inches(2.9), Inches(1.2),
                     "CONTENTS", size=16, color=C_CHAHE,
                     align=PP_ALIGN.CENTER, italic=True, font_name=FONT_KAITI)
            # 右条目
            lines, had = _markdown_to_plain_lines(s_content, max_bullets=20)
            # 目录条目做成竖向多张玻璃卡片
            card_x, card_w, card_top = Inches(4.4), Inches(8.3), Inches(1.15)
            y = card_top
            max_h = Inches(5.4)
            palette_i = 0
            # 清理已空的段落（后续写入 tf）
            if not lines:
                lines = [("bullet", "目录待生成")]
            # 等分高度
            n = max(1, min(8, len(lines)))
            row_h = Emu(int(max_h) // n)
            row_gap = Inches(0.06)
            cur_y = card_top
            for j, (kind, t) in enumerate(lines):
                if cur_y + row_h > card_top + max_h + Inches(0.01):
                    break
                accent = PALETTE_CYCLE[palette_i % len(PALETTE_CYCLE)]; palette_i += 1
                hgt = row_h - row_gap
                _glass_card(slide, card_x, cur_y, card_w, hgt, accent=accent, radius="small")
                # 序号小圆
                from pptx.enum.shapes import MSO_SHAPE
                try:
                    circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, card_x + Inches(0.2), cur_y + (hgt/2) - Inches(0.17), Inches(0.34), Inches(0.34))
                    circ.fill.solid(); circ.fill.fore_color.rgb = accent
                    try: circ.line.fill.background(); circ.shadow.inherit = False
                    except Exception: pass
                    nTb = slide.shapes.add_textbox(card_x + Inches(0.2), cur_y + (hgt/2) - Inches(0.17), Inches(0.34), Inches(0.34))
                    nTf = nTb.text_frame; nTf.margin_left=nTf.margin_right=nTf.margin_top=nTf.margin_bottom=Emu(0)
                    nP = nTf.paragraphs[0]; nP.alignment = PP_ALIGN.CENTER
                    nR = nP.add_run(); nR.text = str(j+1)
                    _set_run_font(nR, FONT_BODY, 12, True, False, C_YUEBAI)
                except Exception:
                    pass
                # 文本
                tbox_x = card_x + Inches(0.7)
                tbox_w = card_w - Inches(0.9)
                tsize = 22 if len(t) < 26 else (20 if len(t) < 40 else 18)
                _textbox(slide, tbox_x, cur_y, tbox_w, hgt, t,
                         size=tsize, color=C_TEXT_DARK,
                         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE,
                         font_name=FONT_TITLE if kind=="title" else FONT_BODY,
                         bold=(kind=="title"))
                cur_y += row_h
            _add_slide_notes(slide, s_notes, s_intent, s_anim, trans_kind, entry_mode)
            continue

        # ===== 普通内页：新知 / 赏析 / 互动 / 练习 / 导入 / 总结 / 作业 =====
        _slide_page_decor(slide, idx, s_anim)
        # 标题玻璃条
        _glass_card(slide, Inches(0.7), Inches(0.85), Inches(11.9), Inches(0.95), accent=C_QINGDAI, radius="small")
        _textbox(slide, Inches(0.9), Inches(0.88), Inches(11.5), Inches(0.9),
                 s_title, size=28, bold=True, color=C_QINGDAI,
                 align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_TITLE)

        # 主体：将 Markdown 拆成元素 → 逐张玻璃卡片渲染
        lines, had_bullets = _markdown_to_plain_lines(s_content, max_bullets=100)
        # 智能分类：quote（玻璃）/ bullet / title / para
        # 布局策略：
        #   - 如果同时含 quote 与 bullet/para → 左 58% 卡片组（quote）/ 右 42%（要点）双栏
        #   - 否则单栏纵向玻璃卡片堆叠
        quotes = [(k, t) for k, t in lines if k == "quote"]
        others = [(k, t) for k, t in lines if k != "quote"]

        content_x = Inches(0.8)
        content_y = Inches(2.00)
        content_w = Inches(11.7)
        content_h = Inches(4.2)

        if quotes and others:
            # 双栏
            lw = Inches(6.5); rw = Inches(4.9)
            # 左：原文/引用玻璃卡
            _glass_card(slide, content_x, content_y, lw, content_h, accent=C_QINGDAI, radius="small")
            lt = slide.shapes.add_textbox(content_x + Inches(0.25), content_y + Inches(0.12),
                                           Inches(1.4), Inches(0.3))
            ltf = lt.text_frame; ltf.margin_left=ltf.margin_right=Emu(0)
            lp = ltf.paragraphs[0]; lp.alignment = PP_ALIGN.LEFT
            lr = lp.add_run(); lr.text = "📖 原文 / 引用"
            _set_run_font(lr, FONT_KAITI, 11, True, False, C_QINGDAI)
            # 正文
            left_tf_box = slide.shapes.add_textbox(content_x + Inches(0.25), content_y + Inches(0.5),
                                                    lw - Inches(0.5), content_h - Inches(0.65))
            ltf2 = left_tf_box.text_frame; ltf2.word_wrap = True; ltf2.vertical_anchor = MSO_ANCHOR.TOP
            # 填内容
            cur_p_l = ltf2.paragraphs[0]; cur_p_l.clear()
            start_l = True
            for k, t in quotes:
                if not start_l: cur_p_l = ltf2.add_paragraph()
                cur_p_l.space_after = Pt(6); cur_p_l.space_before = Pt(2)
                r = cur_p_l.add_run(); r.text = t
                _set_run_font(r, FONT_GUWEN, 16, False, False, C_TEXT_DARK)
                start_l = False
            # 右：要点玻璃卡
            right_x = content_x + lw + Inches(0.3)
            _glass_card(slide, right_x, content_y, rw, content_h, accent=C_ZHUSHA, radius="small")
            rt = slide.shapes.add_textbox(right_x + Inches(0.22), content_y + Inches(0.12),
                                           Inches(2.0), Inches(0.3))
            rtf = rt.text_frame; rtf.margin_left=rtf.margin_right=Emu(0)
            rp = rtf.paragraphs[0]; rp.alignment = PP_ALIGN.LEFT
            rr_ = rp.add_run(); rr_.text = "💡 要点 / 赏析"
            _set_run_font(rr_, FONT_KAITI, 11, True, False, C_ZHUSHA)
            right_tf_box = slide.shapes.add_textbox(right_x + Inches(0.25), content_y + Inches(0.5),
                                                     rw - Inches(0.5), content_h - Inches(0.65))
            rtf2 = right_tf_box.text_frame; rtf2.word_wrap = True; rtf2.vertical_anchor = MSO_ANCHOR.TOP
            cur_p_r = rtf2.paragraphs[0]; cur_p_r.clear()
            start_r = True
            palette_i = 0
            for k, t in others:
                if not start_r: cur_p_r = rtf2.add_paragraph()
                cur_p_r.space_after = Pt(5); cur_p_r.space_before = Pt(2)
                if k == "title":
                    r = cur_p_r.add_run(); r.text = t
                    _set_run_font(r, FONT_TITLE, 17, True, False, C_CHAHE)
                elif k == "bullet":
                    accent = PALETTE_CYCLE[palette_i % len(PALETTE_CYCLE)]; palette_i += 1
                    r = cur_p_r.add_run(); r.text = "●  "
                    _set_run_font(r, FONT_HEITI, 16, True, False, accent)
                    r2 = cur_p_r.add_run(); r2.text = t
                    _set_run_font(r2, FONT_BODY, 15, False, False, C_TEXT_DARK)
                else:  # para / quote-moved
                    r = cur_p_r.add_run(); r.text = t
                    _set_run_font(r, FONT_BODY, 14, False, True, C_CHAHE)
                start_r = False
        else:
            # 单栏：玻璃卡片铺陈（每页最多 6 张）
            elements = lines or [("para", "（该页暂无内容）")]
            # 合并同类型段落，控制卡片数 ≤ 6
            merged = []
            for k, t in elements:
                if merged and merged[-1][0] == k and k in ("para", "quote"):
                    merged[-1] = (k, merged[-1][1] + "\n" + t)
                else:
                    merged.append((k, t))
            if len(merged) > 6:
                merged = merged[:6]
            n = len(merged)
            total_h = content_h
            gap = Inches(0.08)
            card_h = Emu(int(total_h - gap * (n - 1)) // n)
            cur_y = content_y
            palette_i = 0
            for k, t in merged:
                accent = PALETTE_CYCLE[palette_i % len(PALETTE_CYCLE)]; palette_i += 1
                _glass_card(slide, content_x, cur_y, content_w, card_h, accent=accent, radius="small")
                # 标题卡：大一点的字体居中
                if k == "title":
                    _textbox(slide, content_x + Inches(0.35), cur_y, content_w - Inches(0.7), card_h, t,
                             size=22, bold=True, color=accent,
                             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_TITLE)
                elif k == "bullet":
                    # 要点卡片
                    from pptx.enum.shapes import MSO_SHAPE
                    try:
                        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL,
                                                       content_x + Inches(0.25),
                                                       cur_y + (card_h/2) - Inches(0.16),
                                                       Inches(0.32), Inches(0.32))
                        circ.fill.solid(); circ.fill.fore_color.rgb = accent
                        try: circ.line.fill.background(); circ.shadow.inherit = False
                        except Exception: pass
                    except Exception:
                        pass
                    _textbox(slide, content_x + Inches(0.75), cur_y, content_w - Inches(0.95), card_h, t,
                             size=18, color=C_TEXT_DARK,
                             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_BODY)
                elif k == "quote":
                    _textbox(slide, content_x + Inches(0.4), cur_y, content_w - Inches(0.8), card_h, "“" + t + "”",
                             size=16, italic=True, color=C_CHAHE,
                             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_GUWEN)
                else:  # para
                    _textbox(slide, content_x + Inches(0.35), cur_y, content_w - Inches(0.7), card_h, t,
                             size=16, color=C_TEXT_DARK,
                             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_BODY)
                cur_y += card_h + gap

        # 底部：设计意图 + 讲师备注 + 动画 双栏
        foot_y = Inches(6.40)
        foot_h = Inches(0.9)
        if s_intent or s_notes:
            _rounded_rect(slide, Inches(0.8), foot_y, Inches(11.7), foot_h,
                          fill_color=C_MIBAI, line_color=C_GOLD, line_w=Pt(0.75), radius="small")
            mid = Inches(6.6)
            base_left = Inches(0.9)
            if s_intent:
                # 设计意图（左，青黛）
                _textbox(slide, base_left, foot_y, Emu(25400 * 4 // 2), foot_h,
                         "🎯 设计意图", size=11, bold=True, color=C_QINGDAI,
                         anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_KAITI)
                itb = slide.shapes.add_textbox(Inches(2.5), foot_y + Inches(0.05),
                                               Inches(3.8), foot_h - Inches(0.1))
                itf = itb.text_frame; itf.word_wrap = True; itf.vertical_anchor = MSO_ANCHOR.MIDDLE
                ir = itf.paragraphs[0].add_run(); ir.text = s_intent
                _set_run_font(ir, FONT_BODY, 10.5, False, False, C_TEXT_DARK)
                # 分割线
                _rect(slide, mid, Inches(6.46), Emu(9525), Inches(0.78),
                      fill_color=C_GOLD)
            if s_notes:
                # 讲师备注（右，茶褐）
                bx = Inches(6.75) if s_intent else Inches(0.9)
                bw = Inches(5.55) if s_intent else Inches(11.4)
                if s_intent:
                    _textbox(slide, bx, foot_y, Inches(1.3), foot_h,
                             "🗒️ 讲师备注", size=11, bold=True, color=C_CHAHE,
                             anchor=MSO_ANCHOR.MIDDLE, font_name=FONT_KAITI)
                    bx = Inches(8.05); bw = Inches(4.25)
                ntb = slide.shapes.add_textbox(bx, foot_y + Inches(0.05), bw, foot_h - Inches(0.1))
                ntf = ntb.text_frame; ntf.word_wrap = True; ntf.vertical_anchor = MSO_ANCHOR.MIDDLE
                # 处理换行
                lines_n = s_notes.split("\n") if s_notes else [""]
                start = True
                for ln in lines_n:
                    if start:
                        pr = ntf.paragraphs[0]
                        start = False
                    else:
                        pr = ntf.add_paragraph()
                    pr.space_after = Pt(2)
                    rr_ = pr.add_run(); rr_.text = ln
                    _set_run_font(rr_, FONT_BODY, 10.5, False, False, C_TEXT_DARK)
        # notes + 动画（动画收口在 _add_slide_notes 内，避免 continue 漏写）
        _add_slide_notes(slide, s_notes, s_intent, s_anim, trans_kind, entry_mode)

    # 保存到 bytes
    bio = io.BytesIO()
    prs.save(bio)
    bio.seek(0)
    return bio.read()


@router.get("/tools/{run_id}/export_pptx")
def export_tool_as_pptx(run_id: int):
    """按 tool_run ID 导出 .pptx。若该 run 非 PPT 类型且有内容，则也按 ## 页尝试拆分。"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM tool_runs WHERE id=?", (run_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, f"tool_run id={run_id} 不存在")
    row = rows_to_list([row])[0]
    tool_type = row.get("tool_type") or ""
    title = row.get("title") or ("教学文稿-" + str(run_id))
    result = json_loads(row.get("result") or "{}") or {}
    md_text = result.get("markdown") or ""
    slides = result.get("ppt_slides") or []
    if not slides:
        slides = _parse_ppt_slides(md_text) if md_text else []

    theme_info = {
        "subject": result.get("subject") or "",
        "grade": result.get("grade") or "",
        "teacher": (result.get("extra") or "").strip() or "主讲教师",
    }
    try:
        pptx_bytes = _build_pptx_file_bytes(title, slides, theme_info=theme_info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"生成 PPTX 失败：{e}")

    fname = _safe_filename(title, f"教学文稿-{run_id}") + ".pptx"
    import urllib.parse as _urlparse
    encoded = _urlparse.quote(fname, safe="")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
    }
    return StreamingResponse(
        io.BytesIO(pptx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers=headers,
    )
