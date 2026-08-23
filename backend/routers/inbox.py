# -*- coding: utf-8 -*-
"""
收件箱（Inbox）CRUD
note / idea / todo / student
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db import get_cursor, row_to_dict, rows_to_list

router = APIRouter(prefix="")


class InboxCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    type: str = Field(default="note", pattern="^(note|idea|todo|student)$")
    tags: str = ""
    pinned: int = 0


class InboxUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    type: Optional[str] = Field(default=None, pattern="^(note|idea|todo|student|)$")
    tags: Optional[str] = None
    pinned: Optional[int] = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@router.get("/inbox")
def list_inbox(item_type: Optional[str] = None, q: Optional[str] = None):
    sql = "SELECT * FROM inbox_items"
    conds = []
    params = []
    if item_type:
        conds.append("type = ?")
        params.append(item_type)
    if q:
        conds.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY pinned DESC, updated_at DESC, id DESC LIMIT 500"
    with get_cursor() as cur:
        cur.execute(sql, params)
        items = rows_to_list(cur.fetchall())
    return items


@router.get("/inbox/{item_id}")
def get_inbox(item_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM inbox_items WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "不存在的收件箱条目")
        return row_to_dict(row)


@router.post("/inbox")
def create_inbox(data: InboxCreate):
    now = _now()
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO inbox_items
            (title, content, type, tags, pinned, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?)""",
            (data.title, data.content, data.type, data.tags, data.pinned, now, now),
        )
        new_id = cur.lastrowid
    return {"id": new_id, "created_at": now}


@router.put("/inbox/{item_id}")
def update_inbox(item_id: int, data: InboxUpdate):
    # 构建动态 update
    sets = []
    params = []
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is None:
            continue
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        raise HTTPException(400, "未提供任何更新字段")
    sets.append("updated_at = ?")
    params.append(_now())
    params.append(item_id)
    with get_cursor(commit=True) as cur:
        cur.execute(
            f"UPDATE inbox_items SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "不存在的收件箱条目")
    return {"updated": True}


@router.delete("/inbox/{item_id}")
def delete_inbox(item_id: int):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM inbox_items WHERE id = ?", (item_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "不存在的收件箱条目")
    return {"deleted": True}


@router.post("/inbox/{item_id}/pin")
def pin_inbox(item_id: int):
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT pinned FROM inbox_items WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "不存在的收件箱条目")
        new_val = 0 if int(row["pinned"]) == 1 else 1
        cur.execute(
            "UPDATE inbox_items SET pinned = ?, updated_at = ? WHERE id = ?",
            (new_val, _now(), item_id),
        )
    return {"pinned": new_val == 1}
