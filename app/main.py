"""FastAPI 主程序：装配路由、托管前端静态资源、健康检查。

运行： python -m app.main   （默认 0.0.0.0:8000，可用 HOST/PORT 环境变量覆盖）
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import kb, novel, sessions
from app.config import settings
from app.knowledge.store import get_store

settings.ensure_dirs()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI(title="小说创作智能 Agent", version="1.0.0")

app.include_router(sessions.router)
app.include_router(novel.router)
app.include_router(kb.router)

# 静态资源（前端）
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
def health():
    store = get_store()
    return {
        "status": "ok",
        "mock_llm": settings.mock_llm,
        "kb_ready": store.ready,
        "kb_root": str(settings.kb_root_path),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
