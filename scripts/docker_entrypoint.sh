#!/bin/sh
# 容器入口脚本：知识库索引缺失时基于 KB_ROOT 自动构建，再启动服务。
#
# 这样「docker compose up」即可直接使用知识库问答，无需手动预构建；
# 索引一旦生成（落在持久化 volume ./data 中）后续启动会跳过构建。
set -e

INDEX=/app/data/kb/index.json

if [ ! -f "$INDEX" ]; then
  echo "[entrypoint] 未检测到知识库索引 (KB_ROOT=${KB_ROOT:-未设置})，正在构建……"
  if python scripts/build_kb.py; then
    echo "[entrypoint] 知识库构建完成。"
  else
    echo "[entrypoint][警告] 知识库构建失败，问答功能将暂不可用；" \
         "请确认 KB_ROOT 指向正确的素材目录，或启动后调用 POST /api/kb/build 重建。"
  fi
else
  echo "[entrypoint] 已存在知识库索引，跳过构建。"
fi

echo "[entrypoint] 启动 write-agent …"
exec python -m app.main
