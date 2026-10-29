"""知识库构建：扫描写作工作区 → 切片（记录文件名+行号）→ 分词 → BM25 索引（可选稠密向量）。

切片策略：
- 以「空行分隔的段落」为基本单元，天然对应写作素材的语义块；
- 超长段落（>MAX_LINES 行或 >MAX_CHARS 字）按滑动窗口进一步切分，保留行号；
- 每个 chunk 记录：相对路径 doc、起始行 line_start、结束行 line_end、正文 text、分词 tokens；
  稠密模式下额外记录 embed 向量。引用定位精确到「文件 + 行区间」。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from app.config import settings
from app.knowledge.tokenize import tokenize

# 纳入索引的文件类型
SUFFIXES = {".md", ".txt", ".markdown"}
# 跳过这些目录（版本控制、编辑器历史、依赖、缓存等）
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
SKIP_PATH_FRAGMENTS = ("localhistory",)  # 作家助手/LocalHistory 为编辑器产物，不索引

MAX_LINES = 30          # 单 chunk 最大行数
MAX_CHARS = 1600        # 单 chunk 最大字数
WINDOW = 20             # 滑动窗口行数
OVERLAP = 4             # 窗口重叠行数


def _read_text(path: Path) -> str | None:
    """按 UTF-8 / UTF-8-SIG / GBK 依次尝试读取，失败返回 None。"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            return None
    return None


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUFFIXES:
            continue
        parts = set(p.parts)
        if parts & SKIP_DIRS:
            continue
        rel = p.relative_to(root).as_posix()
        if any(frag in rel.lower() for frag in SKIP_PATH_FRAGMENTS):
            continue
        yield p, rel


def _split_chunks(lines: List[str]) -> List[Tuple[int, int, str]]:
    """把文件按段落切片，超长段落再按滑动窗口切分。行号为 1-based。"""
    paras: List[Tuple[int, int, str]] = []
    buf: List[str] = []
    buf_start: int | None = None

    def flush():
        nonlocal buf, buf_start
        if buf:
            text = "\n".join(buf).strip()
            if text:
                paras.append((buf_start, buf_start + len(buf) - 1, text))
            buf = []
            buf_start = None

    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            flush()
        else:
            if buf_start is None:
                buf_start = i
            buf.append(line)
    flush()

    out: List[Tuple[int, int, str]] = []
    for (s, e, t) in paras:
        if (e - s + 1) <= MAX_LINES and len(t) <= MAX_CHARS:
            out.append((s, e, t))
        else:
            out.extend(_window_split(lines, s, e))
    return out


def _window_split(lines: List[str], s: int, e: int) -> List[Tuple[int, int, str]]:
    out: List[Tuple[int, int, str]] = []
    i = s
    while i <= e:
        j = min(i + WINDOW - 1, e)
        text = "\n".join(lines[i - 1 : j]).strip()
        if text:
            out.append((i, j, text))
        if j >= e:
            break
        i = j - OVERLAP + 1
    return out


def build_index(root: Path | None = None, out_dir: Path | None = None) -> Dict:
    """构建知识库索引，落盘到 out_dir，返回统计信息。"""
    root = Path(root or settings.kb_root_path)
    out_dir = Path(out_dir or settings.kb_index_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks: List[Dict] = []
    tokens_corpus: List[List[str]] = []

    for path, rel in _iter_files(root):
        text = _read_text(path)
        if not text:
            continue
        lines = text.split("\n")
        for (s, e, t) in _split_chunks(lines):
            toks = tokenize(t)
            chunks.append(
                {
                    "doc": rel,
                    "line_start": s,
                    "line_end": e,
                    "text": t,
                    "tokens": toks,
                }
            )
            tokens_corpus.append(toks)

    # 稠密向量（可选）
    use_embed = bool(settings.kb_use_embed and settings.embed_base_url
                     and settings.embed_api_key and settings.embed_model)
    emb_matrix = None
    if use_embed:
        from app.llm import llm

        texts = [c["text"] for c in chunks]
        # 分批避免超长
        batch, size = [], 32
        all_emb: List[List[float]] = []
        for i in range(0, len(texts), size):
            all_emb.extend(llm.embed(texts[i : i + size]))
        emb_matrix = np.asarray(all_emb, dtype="float32")
        np.save(out_dir / "embeddings.npy", emb_matrix)

    bm25 = BM25Okapi(tokens_corpus) if tokens_corpus else None

    # 仅持久化必要字段（tokens 一并存，避免重载时重复分词）
    payload = {
        "version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "kb_root": str(root),
        "use_embed": use_embed,
        "embed_model": settings.embed_model if use_embed else "",
        "num_chunks": len(chunks),
        "chunks": [
            {
                "doc": c["doc"],
                "line_start": c["line_start"],
                "line_end": c["line_end"],
                "text": c["text"],
                "tokens": c["tokens"],
            }
            for c in chunks
        ],
    }
    (out_dir / "index.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    # BM25 对象可 pickle 直接落盘，重载更快
    if bm25 is not None:
        import pickle

        (out_dir / "bm25.pkl").write_bytes(pickle.dumps(bm25))

    stats = {
        "kb_root": str(root),
        "num_files": len({c["doc"] for c in chunks}),
        "num_chunks": len(chunks),
        "use_embed": use_embed,
        "embed_model": payload["embed_model"],
        "built_at": payload["built_at"],
        "index_dir": str(out_dir),
    }
    return stats


if __name__ == "__main__":
    import sys

    s = build_index()
    print(json.dumps(s, ensure_ascii=False, indent=2))
