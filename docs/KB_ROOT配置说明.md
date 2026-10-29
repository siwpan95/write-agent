# KB_ROOT 配置说明（给下载者）

`write-agent` 的知识库**不是内置的**——它索引你指定的一个本地写作工作区，问答时逐条标注该工作区里的「文档名 + 片段 + 行号」。这个工作区由环境变量 `KB_ROOT` 指定。

> 仓库默认值 `KB_ROOT=G:/repos/write` 指向作者本机目录，**下载到你机器上并不存在**。克隆后必须先把它改成你自己的素材目录，再构建一次索引，否则知识库问答会返回「未查到」。

---

## 1. 你的素材目录长什么样？

任意一层文件夹即可，`scripts/build_kb.py` 会**递归扫描**其中的文本文件：

```
我的素材/
├── 通用模板包/
│   ├── 黄金三章写法.md
│   └── 人物卡模板.md
├── 参考资料/
│   └── 网文市场趋势.txt
└── 我的小说A/
    ├── bible.md          # 设定集
    └── 大纲.md
```

- **支持的文件类型**：`.md` / `.txt` / `.markdown`（其余忽略）
- **自动跳过的目录**：`.git`、`node_modules`、`__pycache__`、`.venv`、`venv`、`dist`、`build`，以及含 `localhistory` 的路径（编辑器本地历史）
- 不要求特定命名；文件名会作为引用里的「文档名」展示

## 2. 设置 KB_ROOT（三种方式，任选其一）

### 方式 A：写进 `.env`（最常用）

```bash
cp .env.example .env
# 编辑 .env，把这一行改掉：
KB_ROOT=/abs/path/to/我的素材        # Linux / macOS
KB_ROOT=D:/我的素材                  # Windows（用正斜杠或双反斜杠）
```

### 方式 B：仅在本次运行用环境变量

```bash
# Linux / macOS
KB_ROOT=/abs/path/to/我的素材 python -m app.main

# Windows (PowerShell)
$env:KB_ROOT="D:/我的素材"; python -m app.main
```

### 方式 C：Docker / docker-compose

编辑 `docker-compose.yml`，把宿主机素材目录挂进容器，并让 `KB_ROOT` 指向容器内挂载点：

```yaml
services:
  write-agent:
    environment:
      - KB_ROOT=/kb              # 容器内路径
    volumes:
      - /abs/path/to/我的素材:/kb:ro   # 宿主机:容器，只读
```

> 默认 compose 文件挂载的是作者的 `G:/repos/write`。**下载者请改成你自己的绝对路径**（Windows 注意盘符与路径格式）。

## 3. 构建索引

改好 `KB_ROOT` 后，**每次素材有变动都重新构建一次**：

```bash
python scripts/build_kb.py
```

构建产出在 `data/kb/`（已写入 `.gitignore`，**不会**进版本库——索引属于各机器本地产物，应各自构建，不要提交）。

校验是否就绪：

```bash
curl http://127.0.0.1:8000/api/kb/status
# 或
curl http://127.0.0.1:8000/api/health
# 看 kb_ready 字段是否为 true
```

## 4. 不配置素材也能跑（Mock / 演示）

- 即使 `KB_ROOT` 指向空目录或不存在，应用也能启动；只是知识库问答会全部返回「未查到」。
- 想体验界面与创作流程（不加自己的素材）：把 `.env` 的 `MOCK_LLM` 设为 `true`，知识库问答虽无真实资料，但检索、引用组装、会话流转全部真实运作。

## 5. 可选：更强语义召回（稠密向量）

默认仅用 jieba 中文分词 + BM25，**无需联网、无需 embeddings**。若想提升语义召回：

```bash
EMBED_BASE_URL=https://your-embeddings-endpoint/v1
EMBED_API_KEY=sk-xxx
EMBED_MODEL=text-embedding-xxx
KB_USE_EMBED=true
```

然后重新 `python scripts/build_kb.py`（会多一步向量化，需联网调用 embeddings 端点）。

---

## 常见问题

**Q：问答总是「未查到」？**
A：多半是 `KB_ROOT` 没改（仍指向作者路径）、或忘了跑 `build_kb.py`、或素材里确实没有相关词条。先用 `GET /api/kb/status` 确认 `num_chunks > 0`。

**Q：能把 KB_ROOT 设成相对路径吗？**
A：可以，相对路径会相对项目根目录解析（例如 `KB_ROOT=my_corpus` 指向 `write-agent/my_corpus`）。但绝对路径最稳，尤其 Docker 场景。

**Q：索引很大 / 构建很慢？**
A：取决于素材体量；`jieba` 首次加载需分词词典（包内自带，不联网）。纯文本无需 embeddings 时通常几十秒内完成。
