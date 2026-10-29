# syntax=docker/dockerfile:1

# ============================================================
# Stage 1: build & 容器内自测（质量门禁）
#
# 安装开发/测试依赖（requirements-dev.txt —— pip-compile 哈希锁定，
# 每个包带 sha256，--require-hashes 强制校验，防依赖投毒），
# 然后运行 pytest 正式套件 + 自定义冒烟测试（Mock 模式 + 临时语料）。
# 任一测试失败 → 镜像构建直接中断，绝不产出带缺陷的镜像。
# ============================================================
FROM python:3.13-slim AS test
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 开发/测试哈希锁：含运行时依赖 + pytest / httpx / pytest-cov
COPY requirements-dev.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.txt

COPY . .

# 运行时数据目录（pytest 与 ci_smoke 会在其中写入临时索引）
RUN mkdir -p /app/data/kb /app/data/sessions

# 容器内自测：完全自包含，不依赖真实 LLM key 或外部知识库
ENV MOCK_LLM=true
RUN python -m pytest tests/ -q && python scripts/ci_smoke.py

# ============================================================
# Stage 2: runtime（瘦身运行时镜像）
#
# 仅安装生产依赖（requirements.txt，哈希锁定），并从 test 阶段复制
# 已通过自测的代码。知识库索引在首次启动时按需构建（见 entrypoint），
# 因此「docker compose up」即可用，无需手动预构建。
# ============================================================
FROM python:3.13-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MOCK_LLM=false

# 生产哈希锁（仅运行时依赖）
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# 仅复制运行时必需：应用代码 + KB 构建脚本 + 入口脚本 + 配置模板
COPY --from=test /app/app ./app
COPY --from=test /app/scripts ./scripts
COPY --from=test /app/.env.example ./.env.example

RUN sed -i 's/\r$//' /app/scripts/docker_entrypoint.sh \
 && chmod +x /app/scripts/docker_entrypoint.sh \
 && mkdir -p /app/data/kb /app/data/sessions

EXPOSE 8000

# 入口：首次启动时若索引缺失则基于 KB_ROOT 自动构建，随后启动服务
ENTRYPOINT ["./scripts/docker_entrypoint.sh"]
