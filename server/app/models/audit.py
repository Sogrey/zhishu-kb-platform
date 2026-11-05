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


class AuditLog(Base):
    """只增不改的审计日志（FR-11）。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int | None] = mapped_column(Integer, index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, index=True)
    actor_name: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64), index=True)
    detail: Mapped[Any] = mapped_column(_json_type(), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
