from fastapi import APIRouter

from app.api.v1 import audit, auth, chat, documents, eval_api, health, settings_api

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(eval_api.router, prefix="/eval", tags=["eval"])
api_router.include_router(settings_api.router, prefix="/settings", tags=["settings"])
