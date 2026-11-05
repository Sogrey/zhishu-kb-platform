"""文档有效期工具（C-001）。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Document


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validity_state(doc: Document, now: datetime | None = None) -> str:
    """active | pending | expired | retired"""
    if doc.status == "retired" or not doc.is_current:
        if doc.status == "retired":
            return "retired"
    now = now or utcnow()
    vf = doc.valid_from
    vt = doc.valid_to
    if vf is not None and _aware(vf) > now:
        return "pending"
    if vt is not None and _aware(vt) < now:
        return "expired"
    if doc.status == "retired":
        return "retired"
    return "active"


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def validity_sql_clauses(now: datetime | None = None):
    """检索层：未到生效日 / 已过期 均不可见。"""
    now = now or utcnow()
    return (
        or_(Document.valid_from.is_(None), Document.valid_from <= now),
        or_(Document.valid_to.is_(None), Document.valid_to >= now),
        Document.status != "retired",
    )


def retire_expired(db: Session, workspace_id: int | None = None) -> int:
    """将已过期且仍 ready 的文档标为 retired（可定时/手动触发）。"""
    now = utcnow()
    q = db.query(Document).filter(
        Document.status == "ready",
        Document.valid_to.is_not(None),
        Document.valid_to < now,
    )
    if workspace_id is not None:
        q = q.filter(Document.workspace_id == workspace_id)
    n = 0
    for doc in q.all():
        doc.status = "retired"
        doc.is_current = False
        n += 1
    if n:
        db.commit()
    return n
