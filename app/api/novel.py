"""创作工具 API：大纲 / 章节 / 续写 / 改写 / 风格切换 / 剧情走向调整。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent import tools
from app.agent.session import manager

router = APIRouter()


class OutlineReq(BaseModel):
    session_id: str
    theme: str
    genre: str
    style: str
    characters: str


class SessionOnlyReq(BaseModel):
    session_id: str


class RewriteReq(BaseModel):
    session_id: str
    instruction: str
    text: Optional[str] = None


class StyleReq(BaseModel):
    session_id: str
    new_style: str
    text: Optional[str] = None


class AdjustReq(BaseModel):
    session_id: str
    direction: str


def _get_session(sid: str):
    s = manager.get(sid)
    if not s:
        raise HTTPException(status_code=404, detail=f"会话不存在：{sid}")
    return s


@router.post("/api/novel/outline")
def novel_outline(req: OutlineReq):
    s = _get_session(req.session_id)
    text = tools.generate_outline(s, req.theme, req.genre, req.style, req.characters)
    return {"text": text, "story": s.story}


@router.post("/api/novel/chapter")
def novel_chapter(req: SessionOnlyReq):
    s = _get_session(req.session_id)
    text = tools.write_chapter(s)
    return {"text": text, "story": s.story}


@router.post("/api/novel/continue")
def novel_continue(req: SessionOnlyReq):
    s = _get_session(req.session_id)
    text = tools.continue_writing(s)
    return {"text": text, "story": s.story}


@router.post("/api/novel/rewrite")
def novel_rewrite(req: RewriteReq):
    s = _get_session(req.session_id)
    text = tools.rewrite_text(s, req.instruction, req.text)
    return {"text": text, "story": s.story}


@router.post("/api/novel/style")
def novel_style(req: StyleReq):
    s = _get_session(req.session_id)
    text = tools.switch_style(s, req.new_style, req.text)
    return {"text": text, "story": s.story}


@router.post("/api/novel/adjust")
def novel_adjust(req: AdjustReq):
    s = _get_session(req.session_id)
    text = tools.adjust_plot(s, req.direction)
    return {"text": text, "story": s.story}
