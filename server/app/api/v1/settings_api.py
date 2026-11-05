"""系统设置：LLM 推理渠道（admin）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import AuthContext, get_auth
from app.rag import llm_client

router = APIRouter()


def _require_admin(auth: AuthContext) -> None:
    if auth.user.role != "admin":
        raise HTTPException(403, "仅管理员可修改推理设置")


class LlmSettingsUpdate(BaseModel):
    provider: str = Field(..., description="stub|deepseek|ollama|llamacpp")
    base_url: str = ""
    model: str = ""
    api_key: str | None = Field(
        default=None,
        description="不传或空字符串表示保留原 Key；传新值则覆盖",
    )


class ListModelsBody(BaseModel):
    provider: str
    base_url: str = ""
    api_key: str | None = None  # 可临时传未保存的 key 试拉列表


@router.get("/llm")
def get_llm_settings(
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(auth)
    row = llm_client.ensure_llm_settings(db)
    return llm_client.public_view(row)


@router.put("/llm")
def put_llm_settings(
    body: LlmSettingsUpdate,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(auth)
    provider = (body.provider or "").strip().lower()
    if provider not in llm_client.PROVIDERS:
        raise HTTPException(400, f"不支持的渠道: {provider}")

    row = llm_client.ensure_llm_settings(db)
    row.provider = provider
    defaults = llm_client.DEFAULTS.get(provider, {})
    row.base_url = (body.base_url or "").strip() or defaults.get("base_url", "")
    row.model = (body.model or "").strip() or defaults.get("model", "")
    if body.api_key is not None and body.api_key.strip() != "":
        row.api_key = body.api_key.strip()
    elif provider != "deepseek":
        # 非 DeepSeek 清空 key（避免误带）
        if body.api_key is not None and body.api_key.strip() == "":
            row.api_key = None

    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(
        db,
        action="settings.llm_update",
        actor_id=auth.user.id,
        actor_name=auth.user.username,
        workspace_id=auth.workspace_id,
        resource_type="llm_settings",
        resource_id="1",
        detail={"provider": provider, "model": row.model, "base_url": row.base_url},
        commit=True,
    )
    return llm_client.public_view(row)


@router.post("/llm/models")
def post_list_models(
    body: ListModelsBody,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    """按渠道拉取模型列表（Ollama / llama.cpp / DeepSeek）。"""
    _require_admin(auth)
    provider = (body.provider or "").strip().lower()
    if provider == "stub":
        return {"items": []}
    if provider not in llm_client.PROVIDERS:
        raise HTTPException(400, f"不支持的渠道: {provider}")

    row = llm_client.ensure_llm_settings(db)
    base = (body.base_url or "").strip() or row.base_url or llm_client.DEFAULTS[provider]["base_url"]
    key = body.api_key
    if key is None or key.strip() == "":
        key = row.api_key
    try:
        items = llm_client.list_models(provider=provider, base_url=base, api_key=key)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"拉取模型列表失败: {e}") from e
    return {"items": items, "provider": provider, "base_url": base}


@router.post("/llm/test")
def test_llm(
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    """用当前已保存配置发一句极简补全。"""
    _require_admin(auth)
    rt = llm_client.load_runtime(db)
    if not rt.use_llm:
        return {"ok": True, "provider": "stub", "detail": "stub 无需连通测试"}
    text = llm_client.completion_text(
        [{"role": "user", "content": "只回复：pong"}],
        temperature=0,
        timeout=30.0,
        runtime=rt,
    )
    if text is None:
        raise HTTPException(502, "LLM 调用失败，请检查地址 / Key / 模型名")
    return {
        "ok": True,
        "provider": rt.provider,
        "model": rt.model,
        "reply": (text or "")[:200],
    }
