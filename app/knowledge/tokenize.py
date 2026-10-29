"""中文友好的文本分词：优先 jieba，缺失时降级为字符 n-gram，并补抓拉丁词。

BM25 在中文上若直接按空白切分会把整段当一个 token，检索几乎失效；
这里统一在「建库」与「查询」两端使用同一套分词，保证一致性。
"""
from __future__ import annotations

import re

_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_LATIN = re.compile(r"[a-zA-Z0-9]+")

try:  # jieba 为可选但强烈推荐的中文分词器
    import jieba  # type: ignore

    jieba.setLogLevel(60)  # 静默
    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False


def tokenize(text: str) -> list[str]:
    """返回小写 token 列表（去空白），供 BM25 使用。"""
    if not text:
        return []
    tokens: list[str] = []

    if _HAS_JIEBA:
        for w in jieba.lcut(text):
            w = w.strip().lower()
            if w:
                tokens.append(w)
    else:
        # 降级：中文按字符 unigram + bigram，提升无 jieba 时的召回
        chars = [c for c in text if _CJK.match(c)]
        tokens.extend(chars)
        tokens.extend("".join(p) for p in zip(chars, chars[1:]))

    # 拉丁/数字词（中英文混排都能命中）
    tokens.extend(m.group(0).lower() for m in _LATIN.finditer(text))
    # 过滤单字符标点/空白
    return [t for t in tokens if len(t) > 0 and not re.fullmatch(r"[\W_]+", t)]


def has_jieba() -> bool:
    return _HAS_JIEBA
