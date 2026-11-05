"""定时任务执行体：退休扫描 + 金标夜间回归（C-002 / C-104）。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.audit import AuditLog
from app.models.eval import EvalSet
from app.models.user import Workspace
from app.rag.eval_runner import run_eval_set
from app.rag.validity import retire_expired

logger = logging.getLogger(__name__)

# 进程内最近一次执行摘要（API 可读）
_LAST: dict[str, Any] = {
    "retire": None,
    "nightly_eval": None,
}


def get_job_status() -> dict[str, Any]:
    return dict(_LAST)


def _stamp(job: str, payload: dict[str, Any]) -> None:
    _LAST[job] = {**payload, "at": datetime.now(timezone.utc).isoformat()}


def run_retire_scan_all(db: Session | None = None) -> dict[str, Any]:
    own = db is None
    if own:
        db = SessionLocal()
    assert db is not None
    try:
        total = 0
        by_ws: list[dict[str, Any]] = []
        for ws in db.query(Workspace).order_by(Workspace.id.asc()).all():
            n = retire_expired(db, workspace_id=ws.id)
            total += n
            by_ws.append({"workspace_id": ws.id, "name": ws.name, "retired": n})
            db.add(
                AuditLog(
                    workspace_id=ws.id,
                    actor_id=None,
                    actor_name="scheduler",
                    action="document.retire_scan",
                    resource_type="workspace",
                    resource_id=str(ws.id),
                    detail={"retired": n, "source": "scheduler"},
                )
            )
        db.commit()
        out = {"ok": True, "retired": total, "workspaces": by_ws}
        _stamp("retire", out)
        logger.info("retire_scan_all retired=%s", total)
        return out
    except Exception as e:  # noqa: BLE001
        db.rollback()
        err = {"ok": False, "error": str(e)[:500]}
        _stamp("retire", err)
        logger.exception("retire_scan_all failed")
        raise
    finally:
        if own:
            db.close()


def run_nightly_eval_all(
    db: Session | None = None,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """对每个工作区最新/默认金标集跑一轮评测。"""
    own = db is None
    if own:
        db = SessionLocal()
    assert db is not None
    try:
        runs: list[dict[str, Any]] = []
        for ws in db.query(Workspace).order_by(Workspace.id.asc()).all():
            s = (
                db.query(EvalSet)
                .filter(EvalSet.workspace_id == ws.id)
                .order_by(EvalSet.id.desc())
                .first()
            )
            if not s:
                runs.append({"workspace_id": ws.id, "skipped": True, "reason": "no_eval_set"})
                continue
            run = run_eval_set(
                db,
                eval_set=s,
                workspace_id=ws.id,
                clearance=4,
                user_id=None,
                limit=limit,
            )
            db.add(
                AuditLog(
                    workspace_id=ws.id,
                    actor_id=None,
                    actor_name="scheduler",
                    action="eval.nightly",
                    resource_type="eval_run",
                    resource_id=str(run.id),
                    detail={
                        "set_id": s.id,
                        "status": run.status,
                        "pass_rate": (run.metrics or {}).get("pass_rate"),
                        "passed": run.passed_count,
                        "cases": run.case_count,
                        "source": "scheduler",
                    },
                )
            )
            db.commit()
            runs.append(
                {
                    "workspace_id": ws.id,
                    "set_id": s.id,
                    "run_id": run.id,
                    "status": run.status,
                    "metrics": run.metrics,
                    "passed_count": run.passed_count,
                    "case_count": run.case_count,
                }
            )
        out = {"ok": True, "runs": runs}
        _stamp("nightly_eval", out)
        logger.info("nightly_eval done runs=%s", len(runs))
        return out
    except Exception as e:  # noqa: BLE001
        db.rollback()
        err = {"ok": False, "error": str(e)[:500]}
        _stamp("nightly_eval", err)
        logger.exception("nightly_eval failed")
        raise
    finally:
        if own:
            db.close()
