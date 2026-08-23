# -*- coding: utf-8 -*-
"""
文档解析 + 分块
- 支持 .txt / .md / .docx / .pdf
- 分块：600 字，100 字重叠，按字符切（中文友好）
"""
import os
import re
from typing import List, Tuple

import config


# ============ 读取 ============
def _read_txt(path: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_md(path: str) -> str:
    return _read_txt(path)


def _read_docx(path: str) -> str:
    from docx import Document  # python-docx
    doc = Document(path)
    paras = [p.text for p in doc.paragraphs]
    # 也读一下表格文本
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            paras.append(" | ".join(cells))
    return "\n".join([p for p in paras if p])


def _read_pdf(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n\n".join(pages)


def read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        return _read_txt(path) if ext == ".txt" else _read_md(path)
    if ext == ".docx":
        return _read_docx(path)
    if ext == ".pdf":
        return _read_pdf(path)
    # 其他扩展名按 txt 尝试
    return _read_txt(path)


# ============ 分块 ============
def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    return text.strip()


def split_chunks(
    text: str,
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> List[str]:
    """按字符数切分，中文友好（不按词）"""
    text = _clean_text(text)
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    L = len(text)
    while start < L:
        end = min(start + chunk_size, L)
        # 尝试以段落/换行/句号作为切分边界（在 chunk_size 附近）
        if end < L:
            # 向后找最近的结束符
            probe = text[start + chunk_size // 2 : end]
            boundary = None
            for sep in ["\n\n", "\n", "。", "！", "？", ".", "!", "?"]:
                idx = probe.rfind(sep)
                if idx != -1:
                    boundary = start + chunk_size // 2 + idx + len(sep)
                    break
            if boundary and boundary > start + overlap:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= L:
            break
        start = end - overlap
        if start < 0:
            start = 0
        # 防死循环：overlap 为 0 或前进太少
        if start <= (chunks and end - len(chunks[-1]) or 0) - 1:
            start = end
    return chunks


def parse_and_chunk(path: str) -> Tuple[str, List[str]]:
    """返回 (full_text, chunks)"""
    text = read_file(path)
    chunks = split_chunks(text)
    return text, chunks
