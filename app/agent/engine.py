"""Agent 编排：会话入口与模式路由。

- 创作模式（create）：自由对话迭代（调整情节/人物/走向），由 tools.creative_chat 维护上下文；
- 知识库模式（kb）：严格检索问答，由 tools.kb_qa 落实引用硬约束。
具体的大纲/章节/续写/改写/风格切换由 API 直接调用对应工具。
"""
from __future__ import annotations

from typing import Any, Dict

from app.agent import tools
from app.agent.session import Session


def apply_settings(session: Session, **fields) -> Dict[str, Any]:
    """写入新书设定（主题/题材/风格/角色），回写会话状态。"""
    allowed = {"theme", "genre", "style", "characters", "plot_direction"}
    cleaned = {k: v for k, v in fields.items() if k in allowed and v}
    if cleaned:
        session.update_story(**cleaned)
        session.save()
    return session.story


def chat(session: Session, message: str, mode: str) -> Dict:
    """统一对话入口。"""
    if mode == "kb":
        result = tools.kb_qa(session, message)
        return {
            "mode": "kb",
            "answer": result["answer"],
            "citations": result["citations"],
            "has_evidence": result["has_evidence"],
        }
    # create 模式：自由对话迭代
    answer = tools.creative_chat(session, message)
    return {"mode": "create", "answer": answer}
