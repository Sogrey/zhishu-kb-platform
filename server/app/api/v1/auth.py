from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import AuthContext, get_auth, get_current_user
from app.core.security import create_access_token, verify_password
from app.models import User, Workspace, WorkspaceMember

router = APIRouter()


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    workspaces: list[dict]


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> LoginOut:
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(403, "账号已禁用")
    token = create_access_token(user_id=user.id, username=user.username)
    memberships = (
        db.query(WorkspaceMember, Workspace)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .filter(WorkspaceMember.user_id == user.id)
        .all()
    )
    workspaces = [
        {"id": w.id, "name": w.name, "role": m.role} for m, w in memberships
    ]
    write_audit(
        db,
        action="auth.login",
        actor_id=user.id,
        actor_name=user.username,
        workspace_id=workspaces[0]["id"] if workspaces else None,
        resource_type="user",
        resource_id=user.id,
        detail={"clearance": user.clearance},
        ip=request.client.host if request.client else None,
        commit=True,
    )
    return LoginOut(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "clearance": user.clearance,
        },
        workspaces=workspaces,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    memberships = (
        db.query(WorkspaceMember, Workspace)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .filter(WorkspaceMember.user_id == user.id)
        .all()
    )
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "clearance": user.clearance,
        "workspaces": [{"id": w.id, "name": w.name, "role": m.role} for m, w in memberships],
    }


@router.get("/context")
def auth_context(auth: AuthContext = Depends(get_auth)) -> dict:
    return {
        "user_id": auth.user.id,
        "username": auth.user.username,
        "role": auth.user.role,
        "clearance": auth.user.clearance,
        "workspace_id": auth.workspace_id,
    }
