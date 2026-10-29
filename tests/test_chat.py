"""对话入口测试：kb 模式引用/未查到硬约束、create 模式多轮连贯。"""
from __future__ import annotations


def test_kb_chat_with_citations(session_id, client):
    r = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "黄金三章怎么写", "mode": "kb"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["has_evidence"] is True
    assert len(body["citations"]) > 0
    c = body["citations"][0]
    assert {"doc", "line_start", "line_end", "snippet"} <= set(c)


def test_kb_chat_unrelated_not_found(session_id, client):
    r = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "量子计算机运维手册 2026", "mode": "kb"},
    )
    body = r.json()
    assert body["has_evidence"] is False
    assert "未查到" in body["answer"]


def test_create_chat_multiturn(session_id, client):
    r1 = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "把主角改得更腹黑一些", "mode": "create"},
    )
    assert r1.status_code == 200 and len(r1.json()["answer"]) > 10
    r2 = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "再埋一个叛徒伏笔", "mode": "create"},
    )
    assert r2.status_code == 200 and len(r2.json()["answer"]) > 10
