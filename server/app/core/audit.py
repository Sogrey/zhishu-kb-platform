"""审计写入（只增）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    actor_id: int | None = None,
    actor_name: str | None = None,
    workspace_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
    commit: bool = False,
) -> AuditLog:
    row = AuditLog(
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        workspace_id=workspace_id,
        resource_type=resource_type,
        resource_id=None if resource_id is None else str(resource_id),
        detail=detail,
        ip=ip,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row
