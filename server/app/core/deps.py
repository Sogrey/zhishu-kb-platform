from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models.user import User, WorkspaceMember


class AuthContext:
    def __init__(self, user: User, workspace_id: int):
        self.user = user
        self.workspace_id = workspace_id


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(401, "未登录")
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub", 0))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(401, "登录已失效") from exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "用户不可用")
    return user


def get_auth(
    user: User = Depends(get_current_user),
    x_workspace_id: int | None = Header(default=None, alias="X-Workspace-Id"),
    workspace_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AuthContext:
    ws_id = x_workspace_id or workspace_id
    if ws_id is None:
        # 默认取用户第一个工作区
        m = (
            db.query(WorkspaceMember)
            .filter(WorkspaceMember.user_id == user.id)
            .order_by(WorkspaceMember.id.asc())
            .first()
        )
        if not m:
            raise HTTPException(400, "用户未加入任何工作区")
        ws_id = m.workspace_id
    else:
        m = (
            db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.workspace_id == ws_id,
            )
            .first()
        )
        if not m and user.role != "admin":
            raise HTTPException(403, "无权访问该工作区")
    return AuthContext(user=user, workspace_id=int(ws_id))
