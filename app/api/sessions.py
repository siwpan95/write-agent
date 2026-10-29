"""会话与对话 API：会话增删查、模式切换、设定写入、统一对话入口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent import engine
from app.agent.session import manager

router = APIRouter()


class CreateSessionReq(BaseModel):
    title: str = "新会话"


class ModeReq(BaseModel):
    mode: str  # create | kb


class ChatReq(BaseModel):
    session_id: str
    message: str
    mode: Optional[str] = None


class SettingsReq(BaseModel):
    session_id: str
    theme: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    characters: Optional[str] = None
    plot_direction: Optional[str] = None


def _get_session(sid: str):
    s = manager.get(sid)
    if not s:
        raise HTTPException(status_code=404, detail=f"会话不存在：{sid}")
    return s


@router.get("/api/sessions")
def list_sessions():
    return {"sessions": manager.list_sessions()}


@router.post("/api/sessions")
def create_session(req: CreateSessionReq):
    s = manager.create(req.title)
    return s.to_dict()


@router.get("/api/sessions/{sid}")
def get_session(sid: str):
    s = _get_session(sid)
    return s.to_dict()


@router.delete("/api/sessions/{sid}")
def delete_session(sid: str):
    ok = manager.delete(sid)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.post("/api/sessions/{sid}/mode")
def set_mode(sid: str, req: ModeReq):
    s = _get_session(sid)
    if req.mode not in ("create", "kb"):
        raise HTTPException(status_code=400, detail="mode 必须是 create 或 kb")
    s.mode = req.mode
    s.save()
    return {"ok": True, "mode": s.mode}


@router.post("/api/settings")
def apply_settings(req: SettingsReq):
    s = _get_session(req.session_id)
    story = engine.apply_settings(
        s,
        theme=req.theme,
        genre=req.genre,
        style=req.style,
        characters=req.characters,
        plot_direction=req.plot_direction,
    )
    return {"ok": True, "story": story}


@router.post("/api/chat")
def chat(req: ChatReq):
    s = _get_session(req.session_id)
    mode = req.mode or s.mode
    s.mode = mode
    s.save()
    result = engine.chat(s, req.message, mode)
    return result
