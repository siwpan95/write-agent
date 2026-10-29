"""pytest 共享夹具：在导入任何 app.* 之前注入测试环境变量，并用临时语料构建知识库。

本套件完全自包含（Mock LLM + 临时语料），可在 CI 或本地无密钥运行。

关键点：os.environ 必须在 `from app.config import settings` 之前设置，
否则 pydantic-settings 会读取本机可能存在的 .env（真实 key / MOCK_LLM=false），
导致测试误连真实大模型。即使如此，_prepare_kb 夹具仍会强制 settings.mock_llm=True 兜底。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# --- 1) 把项目根加入 sys.path（测试文件需 import app）---
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- 2) 在导入 app 之前准备临时语料与环境变量 ---
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

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.knowledge.ingest import build_index  # noqa: E402
from app.knowledge.store import get_store  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_kb():
    # 防御性再保险：即便本机存在 .env（真实 key / MOCK_LLM=false），也强制 Mock
    settings.mock_llm = True
    settings.llm_api_key = ""
    stats = build_index()
    assert stats["num_chunks"] > 0, f"KB 构建失败：{stats}"
    get_store()  # 触发单例载入
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def session_id(client):
    r = client.post("/api/sessions", json={"title": "pytest"})
    assert r.status_code == 200
    return r.json()["id"]
