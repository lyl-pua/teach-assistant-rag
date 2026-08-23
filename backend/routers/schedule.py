# -*- coding: utf-8 -*-
"""
日程（Schedules）CRUD
category: teach|research|meeting|life|student
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db import get_cursor, row_to_dict, rows_to_list

router = APIRouter(prefix="")

ALLOWED_CATS = {"teach", "research", "meeting", "life", "student"}


class ScheduleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_start: str = ""
    time_end: str = ""
    category: str = Field(default="life")
    done: int = 0


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    category: Optional[str] = None
    done: Optional[int] = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _valid_cat(c: Optional[str]) -> bool:
    return c is None or c in ALLOWED_CATS


@router.get("/schedules")
def list_schedules(
    date: Optional[str] = None,
    from_date: Optional[str] = None,
    to: Optional[str] = None,
    category: Optional[str] = None,
    done: Optional[int] = None,
):
    sql = "SELECT * FROM schedules WHERE 1=1"
    params = []
    if date:
        sql += " AND date = ?"
        params.append(date)
    if from_date:
        sql += " AND date >= ?"
        params.append(from_date)
    if to:
        sql += " AND date <= ?"
        params.append(to)
    if category:
        sql += " AND category = ?"
        params.append(category)
    if done is not None:
        sql += " AND done = ?"
        params.append(int(done))
    sql += " ORDER BY date ASC, time_start ASC, id ASC LIMIT 1000"
    with get_cursor() as cur:
        cur.execute(sql, params)
        return rows_to_list(cur.fetchall())


@router.get("/schedules/{sid}")
def get_schedule(sid: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM schedules WHERE id = ?", (sid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "不存在的日程")
        return row_to_dict(row)


@router.post("/schedules")
def create_schedule(data: ScheduleCreate):
    if not _valid_cat(data.category):
        raise HTTPException(400, f"category 必须是 {ALLOWED_CATS}")
    now = _now()
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO schedules
            (title, content, date, time_start, time_end, category, done, created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (
                data.title, data.content, data.date,
                data.time_start, data.time_end, data.category,
                data.done, now,
            ),
        )
        return {"id": cur.lastrowid, "created_at": now}


@router.put("/schedules/{sid}")
def update_schedule(sid: int, data: ScheduleUpdate):
    sets = []
    params = []
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is None:
            continue
        if k == "category" and not _valid_cat(v):
            raise HTTPException(400, f"category 必须是 {ALLOWED_CATS}")
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        raise HTTPException(400, "未提供任何更新字段")
    params.append(sid)
    with get_cursor(commit=True) as cur:
        cur.execute(
            f"UPDATE schedules SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "不存在的日程")
    return {"updated": True}


@router.delete("/schedules/{sid}")
def delete_schedule(sid: int):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM schedules WHERE id = ?", (sid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "不存在的日程")
    return {"deleted": True}


@router.post("/schedules/{sid}/done")
def toggle_done(sid: int):
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT done FROM schedules WHERE id = ?", (sid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "不存在的日程")
        new_val = 0 if int(row["done"]) == 1 else 1
        cur.execute("UPDATE schedules SET done = ? WHERE id = ?", (new_val, sid))
    return {"done": new_val == 1}
