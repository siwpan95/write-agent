"""会话状态管理：多轮对话上下文 + 作品状态（大纲/角色/剧情走向/最近正文）。

- 每个会话持久化到 data/sessions/<id>.json，重启不丢；
- story_state 用于保持「上下文连贯」与「随时调整剧情走向」。
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


def _now() -> float:
    return time.time()


class Session:
    def __init__(self, session_id: str, title: str = "新会话") -> None:
        self.id = session_id
        self.title = title
        self.mode: str = "create"  # create | kb
        self.messages: List[Dict[str, Any]] = []
        self.story: Dict[str, Any] = {
            "theme": "",
            "genre": "",
            "style": "",
            "characters": "",
            "outline": "",
            "plot_direction": "（未设定，按大纲自然推进）",
            "recent_text": "",
            "current_chapter": "",
        }
        self.created_at: float = _now()
        self.updated_at: float = _now()

    # ---------- 序列化 ----------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "mode": self.mode,
            "messages": self.messages,
            "story": self.story,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Session":
        s = cls(d["id"], d.get("title", "新会话"))
        s.mode = d.get("mode", "create")
        s.messages = d.get("messages", [])
        s.story = d.get("story", s.story)
        s.created_at = d.get("created_at", _now())
        s.updated_at = d.get("updated_at", _now())
        return s

    # ---------- 操作 ----------
    def add_message(
        self,
        role: str,
        content: str,
        citations: Optional[List[Dict]] = None,
        meta: Optional[Dict] = None,
    ) -> None:
        msg = {
            "role": role,
            "content": content,
            "created_at": _now(),
        }
        if citations:
            msg["citations"] = citations
        if meta:
            msg["meta"] = meta
        self.messages.append(msg)
        self.updated_at = _now()

    def update_story(self, **fields) -> None:
        for k, v in fields.items():
            if k in self.story and v is not None:
                self.story[k] = v
        self.updated_at = _now()

    def state_summary(self) -> str:
        s = self.story
        return (
            f"主题：{s['theme'] or '（未设定）'}\n"
            f"题材：{s['genre'] or '（未设定）'}\n"
            f"风格：{s['style'] or '（未设定）'}\n"
            f"角色设定：{s['characters'] or '（未设定）'}\n"
            f"大纲概要：{s['outline'] or '（未生成）'}\n"
            f"剧情走向（最新调整）：{s['plot_direction']}"
        )

    def save(self) -> None:
        settings.sessions_dir.mkdir(parents=True, exist_ok=True)
        path = settings.sessions_dir / f"{self.id}.json"
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class SessionManager:
    def __init__(self) -> None:
        self._cache: Dict[str, Session] = {}

    def _path(self, session_id: str) -> Path:
        return settings.sessions_dir / f"{session_id}.json"

    def create(self, title: str = "新会话") -> Session:
        sid = uuid.uuid4().hex[:12]
        s = Session(sid, title)
        s.save()
        self._cache[sid] = s
        return s

    def get(self, session_id: str) -> Optional[Session]:
        if session_id in self._cache:
            return self._cache[session_id]
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            s = Session.from_dict(json.loads(path.read_text(encoding="utf-8")))
            self._cache[session_id] = s
            return s
        except Exception:
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        settings.sessions_dir.mkdir(parents=True, exist_ok=True)
        out = []
        for p in sorted(
            settings.sessions_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True
        ):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                out.append(
                    {
                        "id": d["id"],
                        "title": d.get("title", "新会话"),
                        "mode": d.get("mode", "create"),
                        "updated_at": d.get("updated_at", 0),
                        "num_messages": len(d.get("messages", [])),
                    }
                )
            except Exception:
                continue
        return out

    def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
            self._cache.pop(session_id, None)
            return True
        return False


manager = SessionManager()
