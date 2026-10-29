"""创作工具：大纲/章节/续写/改写/风格切换 + 知识库问答。

每个工具都会回写会话状态（story），从而保证多轮之间的「上下文连贯」与「剧情走向可调」。
知识库问答在此落实硬约束：无依据 -> 明确「未查到」，且绝不调用模型记忆。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.agent import prompts
from app.agent.session import Session
from app.knowledge import retriever
from app.llm import llm


def _chat(system: str, user: str) -> str:
    return llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}]
    )


# ---------- 创作类 ----------
def generate_outline(
    session: Session,
    theme: str,
    genre: str,
    style: str,
    characters: str,
) -> str:
    session.update_story(theme=theme, genre=genre, style=style, characters=characters)
    system = prompts.system_outline()
    user = prompts.user_outline_input(theme, genre, style, characters)
    text = _chat(system, user)
    session.update_story(outline=text)
    session.add_message("assistant", text, meta={"tool": "outline"})
    session.save()
    return text


def write_chapter(session: Session) -> str:
    system = prompts.system_chapter()
    user = (
        "作品状态：\n"
        + session.state_summary()
        + "\n\n最近正文（承接用）：\n"
        + (session.story.get("recent_text") or "（暂无前文，请直接开篇）")
    )
    text = _chat(system, user)
    # 尝试取首行作为章节标题
    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    session.update_story(recent_text=text, current_chapter=first_line[:60])
    session.add_message("assistant", text, meta={"tool": "chapter"})
    session.save()
    return text


def continue_writing(session: Session) -> str:
    recent = session.story.get("recent_text") or ""
    if not recent:
        return "（尚无正文可续写，请先生成大纲或章节。）"
    system = prompts.system_continue()
    user = "最近正文：\n" + recent
    text = _chat(system, user)
    session.update_story(recent_text=recent + "\n" + text)
    session.add_message("assistant", text, meta={"tool": "continue"})
    session.save()
    return text


def rewrite_text(
    session: Session,
    instruction: str,
    text: Optional[str] = None,
) -> str:
    src = text or session.story.get("recent_text") or ""
    if not src:
        return "（没有可改写的文本，请提供原文或先生成正文。）"
    system = prompts.system_rewrite().format(instruction=instruction, text=src)
    new_text = _chat(system, "请按上述约束改写。")
    session.update_story(recent_text=new_text)
    session.add_message("assistant", new_text, meta={"tool": "rewrite", "instruction": instruction})
    session.save()
    return new_text


def switch_style(
    session: Session,
    new_style: str,
    text: Optional[str] = None,
) -> str:
    src = text or session.story.get("recent_text") or ""
    if not src:
        return "（没有可切换风格的文本，请提供原文或先生成正文。）"
    system = prompts.system_style().format(new_style=new_style, text=src)
    new_text = _chat(system, f"请改写为「{new_style}」风格。")
    session.update_story(style=new_style, recent_text=new_text)
    session.add_message("assistant", new_text, meta={"tool": "style", "new_style": new_style})
    session.save()
    return new_text


def adjust_plot(session: Session, direction: str) -> str:
    """作者随时调整剧情走向：记录到 story.plot_direction，并在后续生成中生效。"""
    session.update_story(plot_direction=direction)
    session.add_message(
        "user", f"[剧情走向调整] {direction}", meta={"tool": "adjust_plot"}
    )
    session.save()
    return f"已记录剧情走向调整：{direction}\n后续创作将遵循该方向。"


# ---------- 知识库问答（硬约束） ----------
def kb_qa(session: Session, question: str) -> Dict:
    ret = retriever.retrieve(question)
    if not ret["has_evidence"]:
        answer = "未查到相关依据，无法基于知识库作答。"
        citations: List[Dict] = []
    else:
        system = prompts.system_kbqa().format(evidence_block=ret["evidence_block"])
        answer = _chat(system, question)
        citations = ret["citations"]
    session.add_message(
        "user", question, meta={"tool": "kb_qa"}
    )
    session.add_message(
        "assistant", answer, citations=citations, meta={"tool": "kb_qa"}
    )
    session.save()
    return {
        "answer": answer,
        "citations": citations,
        "has_evidence": ret["has_evidence"],
        "results": ret["results"],
    }


# ---------- 自由对话（创作模式多轮迭代） ----------
def creative_chat(session: Session, message: str) -> str:
    system = prompts.system_create(session.story)
    # 仅取 role/content，避免把引用等元信息发给模型
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in session.messages
        if m["role"] in ("user", "assistant")
    ]
    messages = [{"role": "system", "content": system}] + history
    messages.append({"role": "user", "content": message})
    # 控制历史长度，避免无限增长
    if len(messages) > 21:
        messages = [messages[0]] + messages[-20:]
    text = llm.chat(messages)
    session.add_message("user", message)
    session.add_message("assistant", text, meta={"tool": "chat"})
    session.save()
    return text
