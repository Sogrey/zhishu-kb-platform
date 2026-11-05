from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "app": s.app_name,
        "env": s.app_env,
        "stub": s.zhishu_dev_stub,
    }
