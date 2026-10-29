"""知识库检索层测试：相关性命中、引用四要素、无关查询判未查到、API 检索。"""
from __future__ import annotations

from app.knowledge.retriever import retrieve


def test_related_query_returns_citations():
    rel = retrieve("黄金三章怎么写", top_k=3)
    assert rel["has_evidence"] is True
    assert len(rel["citations"]) > 0
    c = rel["citations"][0]
    # 引用四要素：文档名 / 起始行 / 结束行 / 片段
    assert {"doc", "line_start", "line_end", "snippet"} <= set(c)
    assert c["line_end"] >= c["line_start"]


def test_unrelated_query_no_evidence():
    irrel = retrieve("量子计算机运维手册 2026", top_k=3)
    assert irrel["has_evidence"] is False
    assert irrel["citations"] == []


def test_kb_query_api(client):
    r = client.post("/api/kb/query", json={"query": "人物小传怎么写", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["has_evidence"] is True
    assert len(body["results"]) > 0
    first = body["results"][0]
    assert {"doc", "line_start", "line_end", "text", "score"} <= set(first)
