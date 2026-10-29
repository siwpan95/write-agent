"""全局配置：基于环境变量（.env）读取，集中管理 LLM / 知识库 / 服务参数。"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（app/ 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 大模型（OpenAI 兼容协议）----------
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.8
    # 无 Key 演示/测试开关：true 时 LLM 返回结构化占位响应
    mock_llm: bool = False

    # ---------- 知识库 ----------
    kb_root: str = "G:/repos/write"          # 待索引的写作工作区
    kb_top_k: int = 6                        # 每次检索返回的最大片段数
    kb_relevance_min: float = 0.3            # 相关性闸门：归一化 BM25 分数下限（0~1）
    kb_coverage_min: float = 0.3             # 相关性闸门：查询词在命中片段中的覆盖率下限（0~1）
    kb_use_embed: bool = False               # 是否启用稠密向量融合
    embed_base_url: str = ""                 # 可选：OpenAI 兼容 embeddings 端点
    embed_api_key: str = ""
    embed_model: str = ""

    # ---------- 服务 ----------
    host: str = "0.0.0.0"
    port: int = 8000

    # ---------- 路径 ----------
    data_dir: Path = BASE_DIR / "data"
    kb_index_dir: Path = BASE_DIR / "data" / "kb"
    sessions_dir: Path = BASE_DIR / "data" / "sessions"

    @property
    def kb_root_path(self) -> Path:
        """知识库根目录（支持相对路径，相对项目根解析）。"""
        p = Path(self.kb_root)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.kb_index_dir, self.sessions_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
