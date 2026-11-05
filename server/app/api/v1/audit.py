from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import AuthContext, get_auth
from app.models import AuditLog

router = APIRouter()


def _require_auditor(auth: AuthContext) -> None:
    if auth.user.role not in {"admin", "auditor", "librarian"}:
        raise HTTPException(403, "无权查看审计日志")


@router.get("")
def list_audits(
    action: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_auditor(auth)
    q = db.query(AuditLog).filter(
        (AuditLog.workspace_id == auth.workspace_id) | (AuditLog.workspace_id.is_(None))
    )
    if action:
        q = q.filter(AuditLog.action == action)
    if actor:
        q = q.filter(AuditLog.actor_name.ilike(f"%{actor.strip()}%"))
    if resource_id:
        q = q.filter(AuditLog.resource_id == resource_id)
    rows = q.order_by(AuditLog.id.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": r.id,
                "workspace_id": r.workspace_id,
                "actor_id": r.actor_id,
                "actor_name": r.actor_name,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "detail": r.detail,
                "ip": r.ip,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/export")
def export_audits(
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    limit: int = Query(default=500, ge=1, le=2000),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
):
    _require_auditor(auth)
    rows = (
        db.query(AuditLog)
        .filter(
            (AuditLog.workspace_id == auth.workspace_id) | (AuditLog.workspace_id.is_(None))
        )
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    if format == "json":
        import json

        payload = [
            {
                "id": r.id,
                "workspace_id": r.workspace_id,
                "actor_name": r.actor_name,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "detail": r.detail,
                "ip": r.ip,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="audit-{datetime.utcnow():%Y%m%d}.json"'
            },
        )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["id", "created_at", "actor", "action", "resource_type", "resource_id", "ip", "detail"]
    )
    for r in rows:
        w.writerow(
            [
                r.id,
                r.created_at.isoformat() if r.created_at else "",
                r.actor_name or "",
                r.action,
                r.resource_type or "",
                r.resource_id or "",
                r.ip or "",
                str(r.detail or ""),
            ]
        )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="audit-{datetime.utcnow():%Y%m%d}.csv"'
        },
    )
