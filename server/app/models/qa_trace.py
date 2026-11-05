"""问答全链路 Trace（FR-14 轻量自建，非 Langfuse）。"""

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


class QaTrace(Base):
    __tablename__ = "qa_traces"

    # 对外暴露的 UUID（非自增，便于外链）
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    hit_test_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{name, status, duration_ms, meta?}, ...]
    spans: Mapped[Any] = mapped_column(_json_type(), nullable=False, default=list)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
