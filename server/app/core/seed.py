import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, Workspace, WorkspaceMember
from app.models.eval import EvalCase, EvalSet

logger = logging.getLogger(__name__)

_GOLD = Path(__file__).resolve().parents[3] / "fixtures" / "eval_gold_v0.json"


def _ensure_workspace(db: Session, name: str, description: str) -> Workspace:
    ws = db.query(Workspace).filter(Workspace.name == name).first()
    if not ws:
        ws = Workspace(name=name, description=description)
        db.add(ws)
        db.flush()
    return ws


def _ensure_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    role: str,
    clearance: int,
) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            role=role,
            clearance=clearance,
        )
        db.add(user)
        db.flush()
    return user


def _ensure_membership(
    db: Session, *, workspace_id: int, user_id: int, role: str
) -> None:
    link = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )
    if not link:
        db.add(
            WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user_id,
                role=role,
            )
        )


def seed_defaults(db: Session) -> None:
    """默认工作区、隔离演示区、admin(L4) / member(L2)。"""
    ws_default = _ensure_workspace(db, "默认工作区", "知枢默认空间")
    ws_iso = _ensure_workspace(db, "制度隔离区", "演示跨工作区隔离（仅管理员）")

    admin = _ensure_user(
        db,
        username="admin",
        display_name="管理员",
        password="admin123",
        role="admin",
        clearance=4,
    )
    member = _ensure_user(
        db,
        username="member",
        display_name="普通成员",
        password="member123",
        role="member",
        clearance=2,
    )

    _ensure_membership(db, workspace_id=ws_default.id, user_id=admin.id, role="admin")
    _ensure_membership(db, workspace_id=ws_iso.id, user_id=admin.id, role="admin")
    _ensure_membership(db, workspace_id=ws_default.id, user_id=member.id, role="member")
    # member 故意不加入「制度隔离区」，用于演示无权工作区 403

    _seed_eval_gold(db, ws_default.id)

    from app.rag.llm_client import ensure_llm_settings

    ensure_llm_settings(db)

    db.commit()
    logger.info(
        "seed ready: admin/admin123 (L4, 2 WS), member/member123 (L2, default only); "
        "ws=%s,%s",
        ws_default.id,
        ws_iso.id,
    )


def _seed_eval_gold(db: Session, workspace_id: int) -> None:
    """导入 fixtures/eval_gold_v0.json；已存在则按 question 补齐新增用例。"""
    if not _GOLD.exists():
        logger.warning("eval gold fixture missing: %s", _GOLD)
        return
    data = json.loads(_GOLD.read_text(encoding="utf-8"))
    cases = data.get("cases") or []
    s = (
        db.query(EvalSet)
        .filter(
            EvalSet.workspace_id == workspace_id,
            EvalSet.name == (data.get("name") or "知枢金标 v0"),
            EvalSet.version == (data.get("version") or "v0"),
        )
        .first()
    )
    if not s:
        s = EvalSet(
            workspace_id=workspace_id,
            name=data.get("name") or "知枢金标 v0",
            version=data.get("version") or "v0",
            description=data.get("description"),
        )
        db.add(s)
        db.flush()
    else:
        if data.get("description"):
            s.description = data["description"]

    existing_q = {
        q
        for (q,) in db.query(EvalCase.question).filter(EvalCase.set_id == s.id).all()
    }
    added = 0
    for c in cases:
        q = c.get("question") or ""
        if not q or q in existing_q:
            continue
        db.add(
            EvalCase(
                set_id=s.id,
                question=q,
                expected_answer=c.get("expected_answer"),
                expected_doc_titles=c.get("expected_doc_titles") or [],
                tags=c.get("tags") or [],
                active=True,
            )
        )
        added += 1
    logger.info(
        "eval gold v0 ready: fixture=%s added=%s set_id=%s",
        len(cases),
        added,
        s.id,
    )
