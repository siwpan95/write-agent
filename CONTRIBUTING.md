# 贡献指南（CONTRIBUTING）

感谢你考虑为 **write-agent** 贡献力量！本文档说明从环境搭建到提交 PR 的完整开发流程。
如果你只是想**使用**本项目，请直接阅读 [README.md](README.md)。

---

## 1. 开发环境准备

要求：Python 3.11+（CI 与 Docker 使用 3.13），建议使用 Git Bash / WSL / MinGW 以获得 `make` 支持。

```bash
git clone <本仓库地址> write-agent
cd write-agent

python -m venv .venv
.venv/Scripts/activate          # Windows
# Linux/macOS: source .venv/bin/activate

# 安装开发/测试依赖（哈希锁定，含运行时 + pytest/httpx/pytest-cov）
pip install --require-hashes -r requirements-dev.txt
# 不带 --require-hashes 也可正常安装（pip 会忽略哈希行，兼容性不变）
```

> 没有 `make`？下方每条命令都给出了等价原始命令，可直接复制执行。

---

## 2. 本地运行与知识库

```bash
cp .env.example .env            # 填入 LLM_API_KEY；或保持 MOCK_LLM=true 演示
python scripts/build_kb.py      # 首次必须：构建知识库索引（写入 data/kb/）
python -m app.main              # 启动，默认 http://127.0.0.1:8000
```

- **知识库问答的素材目录由 `KB_ROOT` 决定**。仓库默认 `KB_ROOT=G:/repos/write` 是作者本机路径，你机器上不存在。克隆后请改 `.env` 里的 `KB_ROOT` 指向你自己的素材目录，再运行 `python scripts/build_kb.py`。详见 [docs/KB_ROOT配置说明.md](docs/KB_ROOT配置说明.md)。
- **Mock 模式**（`MOCK_LLM=true`）：无需任何 key 即可跑通全链路，大模型层返回明确标注「演示模式」的占位响应；知识库检索、引用组装、会话流转全部真实运作。本地开发调试强烈建议先用 Mock 验证逻辑，再切真实 key。

---

## 3. 测试

两套测试均**完全自包含**（临时语料 + `MOCK_LLM=true`），不依赖真实知识库或 LLM key：

| 命令 | 说明 |
| --- | --- |
| `python -m pytest tests/ -q` | 正式 pytest 套件（检索/引用四要素/未查到闸门、大纲/章节/续写/改写/风格/走向、kb 与 create 双模式对话） |
| `python scripts/ci_smoke.py` | 框架无关的冒烟（经 FastAPI TestClient，23 项断言） |

`make` 入口：

```bash
make test        # pytest 套件
make smoke       # 冒烟测试
make ci          # 等价于 CI：test + smoke
```

> 添加新功能时，请同步补充测试。检索/引用相关的改动务必覆盖「无关查询 → 未查到」的闸门，确保知识库问答**永不退化为模型记忆**。

---

## 4. 预提交质量门禁

仓库内置 `.githooks/pre-commit`，提交前自动跑 `pytest` + 冒烟，任一失败即阻断提交。

```bash
make hooks-install     # 安装到 .git/hooks/pre-commit
# 等价于：cp .githooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

钩子逻辑：检测到 `.venv` 才执行测试；若尚未建虚拟环境则优雅跳过（提示先 `make install-dev`）。
紧急情况可用 `git commit --no-verify` 跳过，但请务必在推送前本地补跑 `make ci`。

---

## 5. 依赖管理与供应链加固

依赖采用 **pip-tools 哈希锁定**：`.in` 是人工维护的顶层源，`requirements-*.txt` 是由 `pip-compile --generate-hashes` 生成的锁文件，每个包带跨平台（win/manylinux/macos）的 `sha256`。

| 文件 | 作用 |
| --- | --- |
| `requirements.in` | 顶层运行时依赖（直接编辑版本约束） |
| `requirements.txt` | 运行时哈希锁（生产 / Docker runtime 阶段） |
| `requirements-dev.in` | 开发/测试依赖（含运行时，自包含） |
| `requirements-dev.txt` | 开发哈希锁（CI / 测试 / Docker test 阶段） |

修改依赖的标准流程：

```bash
# 1) 编辑对应的 .in 文件（如新增一个运行时库 → requirements.in）
# 2) 重新生成两份锁文件
make lock
# 等价于：
#   python -m piptools compile --generate-hashes -o requirements.txt requirements.in
#   python -m piptools compile --generate-hashes -o requirements-dev.txt requirements-dev.in
# 3) 在本机 venv 安装验证：pip install --require-hashes -r requirements-dev.txt
# 4) 提交时 .in 与 .txt 一起提交（**不要只提交 .in**）
```

`--require-hashes` 强制校验每个包的哈希，可有效防依赖投毒；不带该参数时 pip 会忽略哈希行照常安装，兼容性不变。

> 锁文件内嵌了 PyPI 镜像源（`pypi.tuna.tsinghua.edu.cn`）。若在境外构建 Docker / 安装依赖较慢，可将镜像改回官方源后重新 `make lock`。

---

## 6. 持续集成

两份等价的流水线都会在 push 时执行 `pytest` + 冒烟：

- **GitHub Actions**：`.github/workflows/ci.yml`（push/PR 到 `master`/`main`）
- **Gitee Go**：`.workflow/ci.yml`（push 到 `master`/`main`）

> **Gitee Go 需你在 Gitee 网页手动开通一次**：仓库「DevOps → Gitee Go」开通并绑定构建资源后，会自动识别 `.workflow/` 配置并在 push 时触发。GUI 可能把配置重写为其规范格式，属正常现象。

Docker 镜像本身也是**质量门禁**：多阶段构建的 `test` 阶段会在镜像内跑 `pytest` + 冒烟，任一测试失败则镜像构建直接中断，不会产出带缺陷的镜像。

---

## 7. 分支与提交约定

- 默认主分支：`master`。
- 功能开发请新建分支（如 `feat/kb-embed`、`fix/rewrite-prompt`），完成后发起 PR / 推送。
- 提交信息建议遵循 `type: 简述` 风格：`feat` / `fix` / `docs` / `test` / `chore` / `refactor`。
- 知识库问答相关的提示词与检索逻辑修改，必须附带能验证「引用四要素 + 未查到闸门」的测试。

---

## 8. 代码风格与结构约定

- 后端：FastAPI（`app/`），配置集中在 `app/config.py`，大模型客户端在 `app/llm.py`（含 Mock 分支）。
- 知识库：`app/knowledge/` 下 `tokenize`（中文分词）→ `ingest`（切片+行号）→ `store`（检索）→ `retriever`（引用组装）。**引用四要素（doc / line_start / line_end / snippet）必须在检索层生成，与模型文本解耦**，确保可复核。
- 编排与工具：`app/agent/`（session / prompts / tools / engine）。新增创作能力请挂到 `tools.py` 并补充对应 `/api/novel/*` 路由。
- 前端：原生 `app/static/`（index.html / app.js / style.css），无构建步骤。
- 知识库问答（`kb` 模式）的硬约束：**只依据检索资料作答、逐条标注依据、无依据即回复「未查到」、严禁调用模型外部知识或记忆**。任何改动都不得破坏这条约束。

---

## 9. 常见问题

- **测试报连真实大模型？** 检查本机是否有 `.env` 残留 `MOCK_LLM=false` / 真实 key。`conftest.py` 与 `ci_smoke.py` 已在导入 app 前强制注入 `MOCK_LLM=true` 兜底，正常情况下不会。
- **知识库问答返回「未查到」？** 先确认 `KB_ROOT` 指向的目录里确有 `.md/.txt/.markdown` 素材，并已 `python scripts/build_kb.py` 构建；再通过 `GET /api/kb/status` 与 `POST /api/kb/query` 核对索引与检索结果。
- **Docker 构建很慢？** `test` 阶段会装开发依赖并跑测试；可改用 `docker build --target runtime .` 跳过自测直接产出运行时镜像（不推荐用于正式发布）。

欢迎提 Issue 与 PR！
