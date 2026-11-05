"""组装并落库问答 Trace（FR-14 轻量）。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import QaTrace


def new_trace_id() -> str:
    return str(uuid.uuid4())


def persist_qa_trace(
    db: Session,
    *,
    trace_id: str,
    workspace_id: int,
    user_id: int | None,
    conversation_id: int | None,
    hit_test_id: int | None,
    query: str,
    answer: str,
    spans: list[dict[str, Any]],
    latency_ms: int,
    message_id: int | None = None,
) -> QaTrace:
    row = QaTrace(
        id=trace_id,
        workspace_id=workspace_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        hit_test_id=hit_test_id,
        query=query,
        answer_preview=(answer or "")[:400],
        spans=spans,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def bind_message(db: Session, trace_id: str, message_id: int) -> None:
    row = db.get(QaTrace, trace_id)
    if not row:
        return
    row.message_id = message_id
    db.commit()
