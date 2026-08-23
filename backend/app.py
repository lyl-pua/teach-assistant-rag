# -*- coding: utf-8 -*-
"""
FastAPI 主入口
- CORS 全放行
- 所有 router 以 /api 前缀挂载
- 启动事件：init_db + load vectorstore
- 若 ../frontend 存在，挂载静态 "/"
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config

# ================ Lifespan ================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    from db import init_db
    from rag.vectorstore import get_vector_store

    # 1) 初始化 DB（建表 + 默认 settings + 让 config 从 DB reload）
    init_db()

    # 2) 加载向量库（不存在则新建空的）
    try:
        _vs = get_vector_store()
        print(f"[startup] 向量库加载完成：{_vs.total_chunks} chunks")
    except Exception as e:
        print(f"[startup] 向量库加载失败（可能 faiss-cpu 未装？）：{e}")

    yield
    # 关闭（此处无需特别处理）


# ================ App ================
app = FastAPI(
    title="教学助手 RAG 后端",
    version=config.APP_VERSION,
    lifespan=lifespan,
)

# CORS 全放行
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ================ Routers（统一 /api 前缀）================
from routers import (
    health as r_health,
    inbox as r_inbox,
    schedule as r_schedule,
    reading as r_reading,
    ai as r_ai,
    tools as r_tools,
    settings as r_settings,
    weather as r_weather,
)

app.include_router(r_health.router, prefix="/api")
app.include_router(r_inbox.router, prefix="/api")
app.include_router(r_schedule.router, prefix="/api")
app.include_router(r_reading.router, prefix="/api")
app.include_router(r_ai.router, prefix="/api")
app.include_router(r_tools.router, prefix="/api")
app.include_router(r_settings.router, prefix="/api")
app.include_router(r_weather.router, prefix="/api")


# ================ 错误兜底（503 未配置 Key）================
# 具体的"503 未配置 API Key"由各 LLM/Embedding 调用点的异常/降级处理；
# 这里保留一个简单的全局异常兜底。
from fastapi.responses import JSONResponse
from fastapi import Request


@app.exception_handler(RuntimeError)
async def runtime_handler(request: Request, exc: RuntimeError):
    msg = str(exc)
    # 包含"未配置.*API Key"关键词 → 503
    if "未配置" in msg and "API Key" in msg:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "后端未配置 API Key，请在设置页填写",
                "raw": msg,
            },
        )
    return JSONResponse(status_code=500, content={"detail": msg})


# ================ 静态文件（放到最后，以确保 /api 路由优先）================
_FRONTEND_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
)
if os.path.isdir(_FRONTEND_DIR):
    # 自定义 StaticFiles 支持 html=True（spa 回退到 index.html）
    class SPAStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            try:
                resp = await super().get_response(path, scope)
                return resp
            except Exception:
                # 回退到 /index.html
                return await super().get_response("index.html", scope)

    app.mount("/", SPAStaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
    print(f"[startup] 已挂载前端静态目录 → {_FRONTEND_DIR}")
else:
    print(f"[startup] 前端目录不存在（跳过静态挂载）：{_FRONTEND_DIR}")


# ================ 根信息（兜底）================
@app.get("/", include_in_schema=False)
def root_info():
    return {
        "name": "教学助手 RAG 后端",
        "version": config.APP_VERSION,
        "docs": "/docs",
        "api_health": "/api/health",
    }
