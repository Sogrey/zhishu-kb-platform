"""LLM 推理渠道配置（单行表，id 固定为 1）。"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.db import Base

_settings = get_settings()


def _json_type():
    if _settings.use_sqlite:
        from sqlalchemy import JSON

        return JSON
    from sqlalchemy.dialects.postgresql import JSONB

    return JSONB


class LlmSettings(Base):
    __tablename__ = "llm_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 恒为 1
    # stub | deepseek | ollama | llamacpp
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="stub")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    # 预留：temperature 等
    extra: Mapped[Any] = mapped_column(_json_type(), nullable=True, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
