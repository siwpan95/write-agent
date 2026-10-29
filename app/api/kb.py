"""知识库 API：状态查询、构建索引、直接检索（调试/前端可直接调用检索）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.knowledge import ingest
from app.knowledge import retriever
from app.knowledge.store import get_store

router = APIRouter()


class QueryReq(BaseModel):
    query: str
    top_k: Optional[int] = None


@router.get("/api/kb/status")
def kb_status():
    store = get_store()
    return store.status()


@router.post("/api/kb/build")
def kb_build():
    """（重新）构建知识库索引。会扫描 KB_ROOT 下的文本素材。"""
    stats = ingest.build_index()
    # 重建后强制重载单例
    store = get_store()
    store.ready = False
    store.load()
    return {"ok": True, "stats": stats}


@router.post("/api/kb/query")
def kb_query(req: QueryReq):
    """直接检索（不调用大模型），返回命中片段与引用，便于核对检索质量。"""
    return retriever.retrieve(req.query, top_k=req.top_k)
