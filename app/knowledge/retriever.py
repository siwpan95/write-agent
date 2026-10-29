"""检索上层：把 store 的候选结果组装为「引用依据」与「证据文本」。

硬约束落地处：
- 检索不到任何命中、或命中未通过相关性闸门（has_evidence=False）→ 上层必须回复「未查到」，
  不得调用模型记忆作答；
- 每条引用必须含：文档名(doc)、具体片段(text 摘要)、原文定位位置(行区间 line_start-line_end)。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from app.config import settings
from app.knowledge.store import get_store, KnowledgeStore
from app.knowledge.tokenize import tokenize

MAX_SNIPPET = 320  # 引用片段展示字数上限


def _snippet(text: str) -> str:
    text = text.replace("\r", "").strip()
    if len(text) <= MAX_SNIPPET:
        return text
    return text[:MAX_SNIPPET] + " ……"


def _relevance_gate(store: KnowledgeStore, raw: List[Dict], query: str) -> bool:
    """双重闸门：归一化 BM25 分数 + 查询词覆盖率。

    纯词面 BM25 对无关查询也会返回命中（如「量子计算机」因含「手册」被命中），
    故用两道可解释阈值判定「是否真有依据」：
      - norm  = top_score / Σidf(查询词)：越高表示命中文档越贴合查询专属词；
      - coverage = 查询词在 top-K 命中片段并集里的覆盖率。
    两者任一不达标即视为无依据，避免把弱命中当答案来源。
    """
    if not raw or store.bm25 is None:
        return False
    q_tokens = list(dict.fromkeys(tokenize(query)))
    if not q_tokens:
        return False
    idf_sum = sum(max(0.0, store.bm25.idf.get(t, 0.0)) for t in q_tokens) or 1e-9
    norm = raw[0]["score"] / idf_sum

    union: set[str] = set()
    for r in raw:
        union.update(store.chunks[r["idx"]]["tokens"])
    coverage = len(set(q_tokens) & union) / len(q_tokens)

    # 关键区分度规则：最具区分度的两个稀有查询词，至少一个须出现在命中片段。
    # 这能把「量子计算机运维手册」这类「含个别词但语义无关」的弱命中挡掉，
    # 而真实相关查询的专属词（黄金三章 / 小传 / 废土旅法师 …）必然命中。
    rare_sorted = sorted(q_tokens, key=lambda t: max(0.0, store.bm25.idf.get(t, 0.0)), reverse=True)
    key_present = any(t in union for t in rare_sorted[:2])

    return (
        norm >= settings.kb_relevance_min
        and coverage >= settings.kb_coverage_min
        and key_present
    )


def retrieve(query: str, top_k: Optional[int] = None) -> Dict:
    """返回检索结果包：
    {
      has_evidence: bool,
      results: [{doc, line_start, line_end, text, snippet, score, kind}],
      citations: [{index, doc, line_start, line_end, snippet}],
      evidence_block: str   # 注入给大模型的带标号证据文本
    }
    """
    store: KnowledgeStore = get_store()
    raw = store.search(query, top_k=top_k)
    has_evidence = _relevance_gate(store, raw, query)

    # 闸门未过：不返回任何命中，强制上层回「未查到」
    if not has_evidence:
        return {
            "has_evidence": False,
            "results": [],
            "citations": [],
            "evidence_block": "",
        }

    results = []
    citations = []
    for i, r in enumerate(raw, start=1):
        entry = {
            "doc": r["doc"],
            "line_start": r["line_start"],
            "line_end": r["line_end"],
            "text": r["text"],
            "snippet": _snippet(r["text"]),
            "score": r["score"],
            "kind": r["kind"],
        }
        results.append(entry)
        citations.append(
            {
                "index": i,
                "doc": r["doc"],
                "line_start": r["line_start"],
                "line_end": r["line_end"],
                "snippet": entry["snippet"],
            }
        )

    evidence_block = _format_evidence(raw)
    return {
        "has_evidence": has_evidence,
        "results": results,
        "citations": citations,
        "evidence_block": evidence_block,
    }


def _format_evidence(raw: List[Dict]) -> str:
    """把命中片段格式化为带 [1][2] 标号的证据块，供大模型引用。"""
    if not raw:
        return ""
    lines = []
    for i, r in enumerate(raw, start=1):
        loc = f"{r['doc']}（第 {r['line_start']}–{r['line_end']} 行）"
        lines.append(f"[{i}] 来源：{loc}\n{r['text']}\n")
    return "\n".join(lines)


def retrieve_for_prompt(query: str, top_k: Optional[int] = None) -> Dict:
    """Agent 调用入口：返回 evidence_block 与 citations，便于直接拼装提示词。"""
    return retrieve(query, top_k=top_k)
