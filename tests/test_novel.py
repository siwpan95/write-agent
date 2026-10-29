"""创作工具 API 测试：健康检查、会话、大纲/章节/续写/改写/风格/走向。"""
from __future__ import annotations

OUTLINE = {
    "theme": "废土上的位面旅人",
    "genre": "废土/奇幻",
    "style": "冷硬写实",
    "characters": "主角林烬，机械师",
}


def _seed_outline(client, sid):
    r = client.post("/api/novel/outline", json={"session_id": sid, **OUTLINE})
    assert r.status_code == 200
    return r


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["mock_llm"] is True
    assert body["kb_ready"] is True


def test_create_session(client):
    r = client.post("/api/sessions", json={"title": "pytest 会话"})
    assert r.status_code == 200
    assert "id" in r.json()


def test_outline(session_id, client):
    r = _seed_outline(client, session_id)
    assert len(r.json()["text"]) > 20


def test_chapter_requires_seeded_story(session_id, client):
    _seed_outline(client, session_id)
    r = client.post("/api/novel/chapter", json={"session_id": session_id})
    assert r.status_code == 200
    assert len(r.json()["text"]) > 20


def test_continue(session_id, client):
    _seed_outline(client, session_id)
    r = client.post("/api/novel/continue", json={"session_id": session_id})
    assert r.status_code == 200
    assert len(r.json()["text"]) > 10


def test_rewrite_changes_text(session_id, client):
    r = client.post(
        "/api/novel/rewrite",
        json={
            "session_id": session_id,
            "instruction": "改成更冷硬的短句",
            "text": "他很难过，因为家没了。",
        },
    )
    assert r.status_code == 200
    assert r.json()["text"] != "他很难过，因为家没了。"


def test_style_switch(session_id, client):
    r = client.post(
        "/api/novel/style",
        json={
            "session_id": session_id,
            "new_style": "古龙武侠风",
            "text": "他站在废墟上。",
        },
    )
    assert r.status_code == 200
    assert len(r.json()["text"]) > 5


def test_adjust_records_direction(session_id, client):
    r = client.post(
        "/api/novel/adjust",
        json={"session_id": session_id, "direction": "第三卷改走悲壮牺牲线，主角团减员"},
    )
    assert r.status_code == 200
    assert len(r.json()["text"]) > 10
    plot = r.json()["story"]["plot_direction"]
    assert "悲壮" in plot or "减员" in plot
