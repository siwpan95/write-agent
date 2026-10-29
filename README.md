# 小说创作智能 Agent（write-agent）

一个支持中文网文创作的智能 Agent：依据主题/题材/风格/角色自动生成大纲与章节、多轮对话迭代润色、续写/改写/风格切换，并内置**带严格引用**的知识库问答。

> 面向 `G:\repos\write` 写作工作区设计：知识库直接索引其中的「通用模板包 / 参考资料 / 点子库 / 各书 bible」等素材，问答时逐条标注**文档名 + 片段 + 行号定位**，检索无依据时明确回复「未查到」。

---

## 功能对照

| 需求 | 实现 |
| --- | --- |
| 1. 依据主题/题材/风格/角色生成大纲与章节 | `/api/novel/outline`、`/api/novel/chapter`（写入会话状态并回显） |
| 2. 多轮对话迭代润色情节与人物 | 创作模式自由对话，会话上下文持久化（`/api/chat` + `tools.creative_chat`） |
| 3. 续写 / 改写 / 风格切换 | `/api/novel/continue`、`/rewrite`、`/style` |
| 4. 上下文连贯 + 随时调整剧情走向 | 会话 `story` 状态 + `/api/novel/adjust` 记录走向调整，后续生成立即遵循 |
| 5. 知识库问答（逐条标注依据） | `/api/chat` 切到 `kb` 模式 → 检索 + 引用，见下方「引用硬约束」 |

---

## 目录结构

```
write-agent/
├── app/
│   ├── main.py                # FastAPI 入口（装配路由 + 托管前端）
│   ├── config.py              # 环境变量配置（pydantic-settings）
│   ├── llm.py                 # OpenAI 兼容客户端（默认 DeepSeek）+ Mock 模式
│   ├── knowledge/
│   │   ├── tokenize.py        # 中文分词（jieba，缺失降级字符 n-gram）
│   │   ├── ingest.py          # 切片（记录文件名+行号）+ BM25 索引
│   │   ├── store.py           # 检索（BM25 / 可选稠密向量融合）
│   │   └── retriever.py       # 引用组装（证据块 + 引用列表）
│   ├── agent/
│   │   ├── session.py         # 会话状态与持久化
│   │   ├── prompts.py         # 提示词模板
│   │   ├── tools.py           # 创作工具 + 知识库问答
│   │   └── engine.py          # 对话编排与模式路由
│   └── static/                # 前端单页（index.html / app.js / style.css）
├── scripts/build_kb.py        # 知识库构建 CLI
├── data/                      # 运行时生成（索引、会话），已 gitignore
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── LICENSE                    # MIT
```

---

## 快速开始

### 1) 本地运行

```bash
cd write-agent
python -m venv .venv
.venv/Scripts/activate          # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # 填入 LLM_API_KEY（或保持 MOCK_LLM=true 演示）
python scripts/build_kb.py      # 首次必须：构建知识库索引
python -m app.main              # 启动，默认 http://127.0.0.1:8000
```

浏览器打开 `http://127.0.0.1:8000`。

### 2) Mock 模式（无 Key 也能跑通全链路）

`.env` 中设 `MOCK_LLM=true`。此时大模型层返回**明确标注「演示模式」的占位响应**，知识库检索、引用组装、会话流转全部真实运作——用于本地体验与 CI 验证。配置真实 `LLM_API_KEY` 后即为真实生成。

### 3) Docker 一键部署

```bash
cp .env.example .env           # 填入 LLM_API_KEY，按需调整 KB_ROOT 挂载路径
docker compose up --build      # 访问 http://localhost:8000
```

> Windows(Docker Desktop) 默认挂载 `G:/repos/write`；Linux/macOS 请改 `docker-compose.yml` 为 `/g/repos/write`（或你本机写作工作区绝对路径）。`KB_ROOT` 在容器内指向只读挂载点 `/kb`。

---

## 环境变量（.env）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容端点（DeepSeek / OpenAI / 通义 / 本地 Ollama 均可） |
| `LLM_API_KEY` | 空 | 大模型密钥 |
| `LLM_MODEL` | `deepseek-chat` | 模型名 |
| `LLM_TEMPERATURE` | `0.8` | 生成温度 |
| `MOCK_LLM` | `false` | `true` 时免密钥返回占位响应 |
| `KB_ROOT` | `G:/repos/write` | 待索引的写作工作区路径 |
| `KB_TOP_K` | `6` | 每次检索返回片段数 |
| `KB_RELEVANCE_MIN` | `0.0` | BM25 归一化分数下限（0~1），用于过滤弱相关 |
| `KB_USE_EMBED` | `false` | 是否启用稠密向量融合 |
| `EMBED_BASE_URL` / `EMBED_API_KEY` / `EMBED_MODEL` | 空 | 可选 embeddings 端点（OpenAI 兼容） |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 服务监听 |

启用稠密向量（语义召回更强）只需：配置上述 `EMBED_*` 三项并把 `KB_USE_EMBED=true`，重建索引即可。默认仅 BM25（jieba 中文分词），**无需联网、无需 embeddings**。

---

## 知识库引用「硬约束」（重点）

知识库问答模式（`kb`）强制遵守：

1. **只依据检索资料作答**：提示词明示「不得调用模型外部知识或记忆」；
2. **逐条标注依据**：每条引用含 `文档名`、`原文片段`、`定位位置（第 X–Y 行）`，由检索层返回、与模型文本解耦，可靠可复核；
3. **无依据即拒答**：当检索命中为空（无任何 token 命中或低于阈值），系统回复「未查到相关依据，无法基于知识库作答」，并**严禁**退化为模型记忆；
4. 前端在回答下方以脚注形式渲染全部引用，便于核对。

该约束在 `app/agent/tools.py:kb_qa` 与 `app/knowledge/retriever.py` 落地。

---

## API 速查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查（含 KB 状态） |
| GET | `/api/sessions` | 会话列表 |
| POST | `/api/sessions` | 新建会话 |
| GET/DELETE | `/api/sessions/{id}` | 获取/删除会话 |
| POST | `/api/sessions/{id}/mode` | 切换 `create` / `kb` |
| POST | `/api/settings` | 写入新书设定（主题/题材/风格/角色/走向） |
| POST | `/api/chat` | 统一对话（按 mode 路由创作/问答） |
| POST | `/api/novel/outline` | 生成大纲 |
| POST | `/api/novel/chapter` | 写章节 |
| POST | `/api/novel/continue` | 续写 |
| POST | `/api/novel/rewrite` | 改写（`instruction`） |
| POST | `/api/novel/style` | 风格切换（`new_style`） |
| POST | `/api/novel/adjust` | 调整剧情走向（`direction`） |
| GET | `/api/kb/status` | 知识库状态 |
| POST | `/api/kb/build` | 重建索引 |
| POST | `/api/kb/query` | 直接检索（不调大模型，用于核对） |

---

## 开源与许可

MIT License © 2026 siwpan（全哥游戏工坊）。默认公开、可自由使用与二次分发。
