from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "知枢"
    app_env: str = "dev"
    secret_key: str = "change-me"
    zhishu_dev_stub: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "zhishu"
    postgres_password: str = "zhishu"
    postgres_db: str = "zhishu"
    # 无 Docker/PG 时：USE_SQLITE=1（单人 stub 默认推荐）
    use_sqlite: bool = True
    sqlite_path: str = "./data/zhishu.db"

    valkey_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    files_dir: str = "./data/files"
    upload_max_mb: int = 100

    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "Qwen3-4B-Instruct-2507"
    tei_embed_url: str = "http://localhost:8081"
    tei_rerank_url: str = "http://localhost:8082"
    parse_url: str = "http://localhost:8083"
    embedding_dim: int = 1024

    # 旧稿归并阈值（余弦相似度）
    merge_strong_threshold: float = 0.92
    merge_weak_threshold: float = 0.80

    # C-002 / C-104 调度（stub 进程内线程；正式可用 Celery beat）
    scheduler_enabled: bool = True
    scheduler_stub_fast: bool = True  # stub 下缩短间隔便于验收
    retire_scan_interval_hours: float = 24.0
    eval_nightly_hour: int = 2  # Asia/Shanghai 本地小时
    scheduler_timezone: str = "Asia/Shanghai"

    # C-103 裁判：EVAL_LLM_JUDGE=1 强制走 LLM；非 stub 默认 LLM
    eval_llm_judge: bool = False
    eval_judge_timeout: float = 60.0

    @property
    def sqlite_url(self) -> str:
        path = Path(self.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+pysqlite:///{path.resolve().as_posix()}"

    @property
    def database_url(self) -> str:
        if self.use_sqlite:
            return self.sqlite_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def files_path(self) -> Path:
        path = Path(self.files_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
