# write-agent Makefile —— 给下载者/开发者的统一入口（需 Git Bash / WSL / MinGW 的 make）
# 等价原始命令见各 target 注释；无 make 环境时可直接复制命令执行。
.RECIPEPREFIX = >

PY := $(shell if [ -f .venv/Scripts/python.exe ]; then echo .venv/Scripts/python; elif [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PIP := $(PY) -m pip

.PHONY: help install install-dev lock test smoke ci run kb hooks-install clean

help:
> @echo "write-agent 可用目标："
> @echo "  make install      安装生产依赖（哈希锁定，--require-hashes）"
> @echo "  make install-dev  安装开发/测试依赖（含运行时，哈希锁定）"
> @echo "  make lock         用 pip-compile 重新生成哈希锁文件（需改 .in 后执行）"
> @echo "  make test         运行 pytest 正式套件"
> @echo "  make smoke        运行自包含冒烟测试（Mock + 临时语料）"
> @echo "  make ci           同时执行 test + smoke（等价于 CI）"
> @echo "  make run          启动本地服务（默认 http://127.0.0.1:8000）"
> @echo "  make kb           构建知识库索引（需先配置 KB_ROOT）"
> @echo "  make hooks-install 安装 git 预提交钩子（提交前自动跑测试）"
> @echo "  make clean        清理缓存与运行时数据"

install:
> $(PIP) install --require-hashes -r requirements.txt

install-dev:
> $(PIP) install --require-hashes -r requirements-dev.txt

lock:
> $(PY) -m piptools compile --generate-hashes -o requirements.txt requirements.in
> $(PY) -m piptools compile --generate-hashes -o requirements-dev.txt requirements-dev.in

test:
> $(PY) -m pytest tests/ -q

smoke:
> $(PY) scripts/ci_smoke.py

ci: test smoke

run:
> $(PY) -m app.main

kb:
> $(PY) scripts/build_kb.py

hooks-install:
> cp .githooks/pre-commit .git/hooks/pre-commit
> chmod +x .git/hooks/pre-commit
> @echo "✅ 预提交钩子已安装：每次 git commit 前会自动跑 pytest + ci_smoke（可用 git commit --no-verify 跳过）"

clean:
> find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
> rm -rf data/kb data/sessions *.egg-info build dist 2>/dev/null || true
> @echo "🧹 已清理缓存与运行时数据"
