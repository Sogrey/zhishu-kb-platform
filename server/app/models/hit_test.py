"""Hit Test 运行记录（C-012）：只增，持久化 context_snapshot。"""

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


class HitTestRun(Base):
    __tablename__ = "hit_test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    clearance: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # hit_test | chat
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="hit_test")
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # 分路 id、注入块全文、分数、channels 等
    context_snapshot: Mapped[Any] = mapped_column(_json_type(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
