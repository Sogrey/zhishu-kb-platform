"""评测 API：金标集列表 / 跑评测 / 查看运行结果（M3-2）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import AuthContext, get_auth
from app.core.jobs import run_nightly_eval_all, run_retire_scan_all
from app.core.scheduler import get_scheduler_state
from app.models.eval import EvalCase, EvalRun, EvalRunItem, EvalSet
from app.rag.eval_runner import run_eval_set

router = APIRouter()


def _require_eval(auth: AuthContext) -> None:
    if auth.user.role not in {"admin", "librarian", "auditor"}:
        raise HTTPException(403, "仅管理员/知识管理员/审计员可使用评测")


@router.get("/sets")
def list_sets(
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_eval(auth)
    rows = (
        db.query(EvalSet)
        .filter(EvalSet.workspace_id == auth.workspace_id)
        .order_by(EvalSet.id.desc())
        .all()
    )
    items = []
    for s in rows:
        n = db.query(EvalCase).filter(EvalCase.set_id == s.id, EvalCase.active.is_(True)).count()
        last = (
            db.query(EvalRun)
            .filter(EvalRun.set_id == s.id)
            .order_by(EvalRun.id.desc())
            .first()
        )
        items.append(
            {
                "id": s.id,
                "name": s.name,
                "version": s.version,
                "description": s.description,
                "case_count": n,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "last_run": _run_brief(last) if last else None,
            }
        )
    return {"items": items}


@router.get("/sets/{set_id}/cases")
def list_cases(
    set_id: int,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_eval(auth)
    s = _get_set(db, set_id, auth.workspace_id)
    cases = (
        db.query(EvalCase)
        .filter(EvalCase.set_id == s.id)
        .order_by(EvalCase.id.asc())
        .all()
    )
    return {
        "set": {"id": s.id, "name": s.name, "version": s.version},
        "items": [
            {
                "id": c.id,
                "question": c.question,
                "expected_answer": c.expected_answer,
                "expected_doc_titles": c.expected_doc_titles or [],
                "tags": c.tags or [],
                "active": c.active,
            }
            for c in cases
        ],
    }


@router.post("/sets/{set_id}/run")
def start_run(
    set_id: int,
    limit: int | None = Query(default=None, ge=1, le=200),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_eval(auth)
    s = _get_set(db, set_id, auth.workspace_id)
    try:
        run = run_eval_set(
            db,
            eval_set=s,
            workspace_id=auth.workspace_id,
            clearance=auth.user.clearance,
            user_id=auth.user.id,
            limit=limit,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"评测失败: {e}") from e
    return _run_detail(db, run)


@router.get("/runs")
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_eval(auth)
    rows = (
        db.query(EvalRun)
        .filter(EvalRun.workspace_id == auth.workspace_id)
        .order_by(EvalRun.id.desc())
        .limit(limit)
        .all()
    )
    return {"items": [_run_brief(r) for r in rows]}


@router.get("/dashboard")
def eval_dashboard(
    limit: int = Query(default=30, ge=3, le=100),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    """C-106：跑次趋势序列（时间升序，便于画折线）。"""
    _require_eval(auth)
    rows = (
        db.query(EvalRun)
        .filter(
            EvalRun.workspace_id == auth.workspace_id,
            EvalRun.status == "done",
        )
        .order_by(EvalRun.id.desc())
        .limit(limit)
        .all()
    )
    series_desc = [_run_brief(r) for r in rows]
    series = list(reversed(series_desc))
    latest = series[-1] if series else None
    prev = series[-2] if len(series) >= 2 else None
    keys = [
        "pass_rate",
        "citation_hit",
        "context_recall",
        "answer_relevancy",
        "faithfulness",
    ]
    delta: dict[str, float | None] = {}
    if latest and prev:
        lm = latest.get("metrics") or {}
        pm = prev.get("metrics") or {}
        for k in keys:
            a, b = lm.get(k), pm.get(k)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                delta[k] = round(float(a) - float(b), 4)
            else:
                delta[k] = None
    return {
        "series": series,
        "latest": latest,
        "previous": prev,
        "delta": delta,
        "run_count": len(series),
    }


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_eval(auth)
    run = db.get(EvalRun, run_id)
    if not run or run.workspace_id != auth.workspace_id:
        raise HTTPException(404, "评测运行不存在")
    return _run_detail(db, run)


@router.get("/scheduler")
def scheduler_status(auth: AuthContext = Depends(get_auth)) -> dict:
    _require_eval(auth)
    return get_scheduler_state()


@router.post("/scheduler/retire-now")
def scheduler_retire_now(auth: AuthContext = Depends(get_auth)) -> dict:
    if auth.user.role not in {"admin", "librarian"}:
        raise HTTPException(403, "仅管理员/知识管理员可触发退休扫描")
    return run_retire_scan_all()


@router.post("/scheduler/nightly-now")
def scheduler_nightly_now(
    limit: int | None = Query(default=None, ge=1, le=200),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    _require_eval(auth)
    return run_nightly_eval_all(limit=limit)


def _get_set(db: Session, set_id: int, workspace_id: int) -> EvalSet:
    s = db.get(EvalSet, set_id)
    if not s or s.workspace_id != workspace_id:
        raise HTTPException(404, "评测集不存在")
    return s


def _run_brief(r: EvalRun) -> dict:
    return {
        "id": r.id,
        "set_id": r.set_id,
        "status": r.status,
        "case_count": r.case_count,
        "passed_count": r.passed_count,
        "metrics": r.metrics or {},
        "error_message": r.error_message,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


def _run_detail(db: Session, run: EvalRun) -> dict:
    items = (
        db.query(EvalRunItem)
        .filter(EvalRunItem.run_id == run.id)
        .order_by(EvalRunItem.id.asc())
        .all()
    )
    return {
        **_run_brief(run),
        "items": [
            {
                "id": it.id,
                "case_id": it.case_id,
                "question": it.question,
                "answer": it.answer[:800],
                "hit_doc_titles": it.hit_doc_titles or [],
                "scores": it.scores or {},
                "passed": it.passed,
                "latency_ms": it.latency_ms,
            }
            for it in items
        ],
    }
