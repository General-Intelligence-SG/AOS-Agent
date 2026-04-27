"""AOS 配置管理"""
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── 应用基础 ──
    APP_NAME: str = "AOS 奥思虚拟助理"
    APP_VERSION: str = "0.1.0-poc"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── 数据目录 ──
    DATA_DIR: Path = Path(__file__).parent.parent / "data"
    DB_DIR: Path = DATA_DIR / "db"
    FILES_DIR: Path = DATA_DIR / "files"
    INDEX_DIR: Path = DATA_DIR / "indexes"
    EXPORT_DIR: Path = DATA_DIR / "exports"

    # ── 数据库 ──
    DATABASE_URL: str = ""

    # ── LLM 配置 ──
    LLM_PROVIDER: str = "openai"  # openai / deepseek / qwen / ollama
    LLM_API_KEY: str = ""
    LLM_BASE_URL: Optional[str] = None  # 自定义 API 地址
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.7

    # ── 记忆配置 ──
    MEMORY_SHORT_TERM_WINDOW: int = 20  # 短期记忆保留条数
    MEMORY_VECTOR_DIM: int = 1536  # 向量维度
    MEMORY_SIMILARITY_THRESHOLD: float = 0.75

    # ── 安全配置 ──
    EXPORT_ENCRYPTION_KEY: str = "aos-poc-default-key-change-me"

    # ── 前端 ──
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def model_post_init(self, __context):
        # 确保目录存在
        for d in [self.DATA_DIR, self.DB_DIR, self.FILES_DIR,
                  self.INDEX_DIR, self.EXPORT_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        # 默认数据库路径
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite+aiosqlite:///{self.DB_DIR / 'aos.db'}"
        # 根据 provider 设置默认 base_url
        if not self.LLM_BASE_URL:
            providers = {
                "deepseek": "https://api.deepseek.com/v1",
                "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "ollama": "http://localhost:11434/v1",
            }
            self.LLM_BASE_URL = providers.get(self.LLM_PROVIDER)


settings = Settings()
