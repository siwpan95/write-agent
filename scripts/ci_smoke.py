#!/usr/bin/env python3
"""write-agent 自包含冒烟测试（CI / 本地均可运行）。

不依赖用户本机知识库或真实 LLM key：
- 在临时目录生成极小语料（含「黄金三章」「人物小传」「废土世界观」）；
- MOCK_LLM=true 下构建 BM25 索引并跑通全链路：
  检索与引用、相关性闸门（无依据 → 未查到）、
  大纲/章节/续写/改写/风格切换/剧情走向/多轮对话（经 FastAPI TestClient）。

用法：  python scripts/ci_smoke.py
退出码：0 全部通过；1 存在失败项。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# 必须在 import app.* 之前设置环境变量（app.config 在导入时即读取 env/.env）
# ---------------------------------------------------------------------------
_CORPUS = Path(tempfile.mkdtemp(prefix="wakb_"))
(_CORPUS / "写作方法论.md").write_text(
    "# 黄金三章写作法\n\n"
    "黄金三章指的是小说开头的三章，核心任务是入局、加压、承诺。\n"
    "入局：快速把读者拉进故事世界。\n"
    "加压：制造冲突与悬念。\n"
    "承诺：给出主线承诺，让读者愿意追读。\n\n"
    "# 人物小传怎么写\n\n"
    "人物小传应包含外貌、性格、动机、秘密与成长弧。\n"
    "给每个主要角色写一页小传，明确其欲望与恐惧。\n",
    encoding="utf-8",
)
(_CORPUS / "世界观设定.md").write_text(
    "# 废土世界观\n\n"
    "废土世界以辐射尘、稀缺水源与残破科技为特征。\n"
    "位面旅人在废土与异界之间往返，收集锚点碎片。\n",
    encoding="utf-8",
)

os.environ["KB_ROOT"] = str(_CORPUS)
os.environ["MOCK_LLM"] = "true"
os.environ["KB_USE_EMBED"] = "false"
os.environ["KB_RELEVANCE_MIN"] = "0.0"
os.environ["KB_COVERAGE_MIN"] = "0.0"
os.environ["KB_TOP_K"] = "5"

from fastapi.testclient import TestClient  # noqa: E402

# scripts/ 不在包路径内，运行本脚本时需把项目根加入 sys.path
import sys as _sys  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent  # write-agent/
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))

from app.config import settings  # noqa: E402
from app.knowledge.ingest import build_index  # noqa: E402
from app.knowledge.store import get_store  # noqa: E402
from app.knowledge.retriever import retrieve  # noqa: E402
from app.main import app  # noqa: E402

_FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {msg}")
    if not cond:
        _FAILURES.append(msg)


def main() -> int:
    # 1) 构建 KB（写入默认 data/kb，已被 .gitignore 忽略）
    stats = build_index()
    check(stats["num_chunks"] > 0, f"KB 构建产出切片 {stats['num_chunks']} 个")

    store = get_store()  # 载入刚构建的索引到进程内单例
    check(store.ready, "知识库索引已就绪 (store.ready=True)")

    client = TestClient(app)

    # 2) 健康检查
    r = client.get("/api/health")
    check(r.status_code == 200, "/api/health -> 200")
    hb = r.json()
    check(hb.get("mock_llm") is True, "health.mock_llm == true")
    check(hb.get("kb_ready") is True, "health.kb_ready == true")

    # 3) 检索层：相关查询（应命中并返回引用）
    rel = retrieve("黄金三章怎么写", top_k=3)
    check(rel["has_evidence"] is True, "相关查询 retrieve.has_evidence == True")
    check(len(rel["citations"]) > 0, "相关查询返回引用")
    c0 = rel["citations"][0]
    check(
        {"doc", "line_start", "line_end", "snippet"} <= set(c0),
        "引用含 doc / line_start / line_end / snippet 四要素",
    )

    # 4) 检索层：无关查询（应判未查到，零引用）
    irrel = retrieve("量子计算机运维手册 2026", top_k=3)
    check(irrel["has_evidence"] is False, "无关查询 retrieve.has_evidence == False")
    check(len(irrel["citations"]) == 0, "无关查询零引用")

    # 5) 会话 + 创作全链路（Mock 模式，无网络）
    r = client.post("/api/sessions", json={"title": "CI"})
    check(r.status_code == 200, "POST /api/sessions -> 200")
    sid = r.json()["id"]

    r = client.post(
        "/api/novel/outline",
        json={
            "session_id": sid,
            "theme": "废土上的位面旅人",
            "genre": "废土/奇幻",
            "style": "冷硬写实",
            "characters": "主角林烬，机械师",
        },
    )
    check(r.status_code == 200 and len(r.json().get("text", "")) > 20, "大纲生成非空")

    r = client.post("/api/novel/chapter", json={"session_id": sid})
    check(r.status_code == 200 and len(r.json().get("text", "")) > 20, "章节生成非空")

    r = client.post("/api/novel/continue", json={"session_id": sid})
    check(r.status_code == 200 and len(r.json().get("text", "")) > 10, "续写非空")

    r = client.post(
        "/api/novel/rewrite",
        json={"session_id": sid, "instruction": "改成更冷硬的短句", "text": "他很难过，因为家没了。"},
    )
    check(
        r.status_code == 200 and r.json().get("text", "") != "他很难过，因为家没了。",
        "改写产出不同文本",
    )

    r = client.post(
        "/api/novel/style",
        json={"session_id": sid, "new_style": "古龙武侠风", "text": "他站在废墟上。"},
    )
    check(r.status_code == 200 and len(r.json().get("text", "")) > 5, "风格切换产物非空")

    r = client.post(
        "/api/novel/adjust",
        json={"session_id": sid, "direction": "第三卷改走悲壮牺牲线，主角团减员"},
    )
    check(r.status_code == 200 and len(r.json().get("text", "")) > 10, "调整剧情走向非空")

    # 6) 知识库问答（经 HTTP，kb 模式）
    r = client.post("/api/chat", json={"session_id": sid, "message": "黄金三章怎么写", "mode": "kb"})
    check(r.status_code == 200, "kb 模式对话 -> 200")
    kb = r.json()
    check(kb.get("has_evidence") is True and len(kb.get("citations", [])) > 0, "kb 问答带引用")

    r = client.post(
        "/api/chat", json={"session_id": sid, "message": "量子计算机运维手册 2026", "mode": "kb"}
    )
    kb2 = r.json()
    check(kb2.get("has_evidence") is False, "kb 问答对无关查询判未查到")
    check("未查到" in kb2.get("answer", ""), "kb 问答无关时回复含『未查到』")

    # 7) 创作模式多轮对话
    r = client.post(
        "/api/chat",
        json={"session_id": sid, "message": "把主角改得更腹黑一些", "mode": "create"},
    )
    check(r.status_code == 200 and len(r.json().get("answer", "")) > 10, "创作模式多轮对话非空")

    if _FAILURES:
        print(f"\nCI 冒烟测试失败 {len(_FAILURES)} 项：")
        for f in _FAILURES:
            print("  - " + f)
        return 1
    print("\nCI 冒烟测试全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
