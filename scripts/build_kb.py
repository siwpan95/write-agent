#!/usr/bin/env python
"""知识库构建脚本：扫描 KB_ROOT 下的文本素材并建立索引。

用法：
    python scripts/build_kb.py
等价于调用 app.knowledge.ingest.build_index()，结果写入 data/kb/。
首次启动前务必执行一次；素材更新后重新执行即可重建。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.knowledge import ingest  # noqa: E402


def main() -> None:
    stats = ingest.build_index()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
