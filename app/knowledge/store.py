"""知识库存储与检索：载入索引，提供 BM25（可选稠密向量融合）检索。

检索结果为带「精确定位」的 chunk 列表，供上层组装引用。
「无依据」判定：当所有候选分数为 0（无任何 token 命中）或低于阈值时，返回空结果，
由上层据此回复「未查到」，绝不退化为模型记忆作答。
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.config import settings
from app.knowledge.tokenize import tokenize


class KnowledgeStore:
    def __init__(self) -> None:
        self.chunks: List[Dict] = []
        self.bm25 = None
        self.emb_matrix: Optional[np.ndarray] = None
        self.use_embed = False
        self.ready = False
        self.meta: Dict = {}

    # ---------- 载入 ----------
    def load(self, index_dir: Optional[Path] = None) -> bool:
        index_dir = Path(index_dir or settings.kb_index_dir)
        idx_path = index_dir / "index.json"
        if not idx_path.exists():
            self.ready = False
            return False
        payload = json.loads(idx_path.read_text(encoding="utf-8"))
        self.chunks = payload["chunks"]
        self.meta = {k: v for k, v in payload.items() if k != "chunks"}
        self.use_embed = bool(payload.get("use_embed"))

        bm25_path = index_dir / "bm25.pkl"
        if bm25_path.exists():
            try:
                self.bm25 = pickle.loads(bm25_path.read_bytes())
            except Exception:
                self.bm25 = None

        if self.use_embed:
            emb_path = index_dir / "embeddings.npy"
            if emb_path.exists():
                self.emb_matrix = np.load(emb_path)

        self.ready = len(self.chunks) > 0
        return self.ready

    # ---------- 检索 ----------
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_frac: Optional[float] = None,
    ) -> List[Dict]:
        """返回按相关度排序的候选 chunk（含分数与定位信息）。无依据时返回空列表。"""
        if not self.ready:
            return []
        top_k = top_k or settings.kb_top_k
        min_frac = min_frac if min_frac is not None else settings.kb_relevance_min
        q_tokens = tokenize(query)

        bm25_scores = np.zeros(len(self.chunks), dtype="float32")
        if self.bm25 is not None and q_tokens:
            bm25_scores = np.asarray(self.bm25.get_scores(q_tokens), dtype="float32")

        dense_scores = np.zeros(len(self.chunks), dtype="float32")
        if self.use_embed and self.emb_matrix is not None and query.strip():
            dense_scores = self._dense_scores(query)

        # 融合：BM25 为主，稠密可选（Reciprocal Rank Fusion）
        if self.use_embed and dense_scores.any():
            fused = self._rrf(bm25_scores, dense_scores)
            order = np.argsort(-fused)[:top_k]
            scores = fused[order]
            kinds = ["fused"] * len(order)
        else:
            order = np.argsort(-bm25_scores)[:top_k]
            scores = bm25_scores[order]
            kinds = ["bm25"] * len(order)

        max_score = float(scores.max()) if len(scores) else 0.0
        results: List[Dict] = []
        for rank, idx in enumerate(order):
            sc = float(scores[rank])
            if sc <= 1e-6:  # 完全无命中
                continue
            if min_frac > 0 and max_score > 0 and sc < min_frac * max_score:
                continue
            c = self.chunks[idx]
            results.append(
                {
                    "idx": int(idx),
                    "doc": c["doc"],
                    "line_start": c["line_start"],
                    "line_end": c["line_end"],
                    "text": c["text"],
                    "score": round(sc, 4),
                    "kind": kinds[rank],
                }
            )
        return results

    def _dense_scores(self, query: str) -> np.ndarray:
        from app.llm import llm

        q_emb = np.asarray(llm.embed([query])[0], dtype="float32")
        # 归一化后点积 = 余弦相似度
        qn = q_emb / (np.linalg.norm(q_emb) + 1e-9)
        M = self.emb_matrix / (
            np.linalg.norm(self.emb_matrix, axis=1, keepdims=True) + 1e-9
        )
        return M @ qn

    @staticmethod
    def _rrf(*score_arrays, k: int = 60) -> np.ndarray:
        n = len(score_arrays[0])
        fused = np.zeros(n, dtype="float32")
        for arr in score_arrays:
            order = np.argsort(-arr)
            for rank, idx in enumerate(order):
                if arr[idx] <= 0:
                    continue
                fused[idx] += 1.0 / (k + rank + 1)
        return fused

    def status(self) -> Dict:
        return {
            "ready": self.ready,
            "use_embed": self.use_embed,
            "num_chunks": len(self.chunks),
            "embed_model": self.meta.get("embed_model", ""),
            "built_at": self.meta.get("built_at", ""),
            "kb_root": self.meta.get("kb_root", ""),
        }


# 进程内单例（索引较大，避免重复载入）
_store = KnowledgeStore()


def get_store() -> KnowledgeStore:
    if not _store.ready:
        _store.load()
    return _store
