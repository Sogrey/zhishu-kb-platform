import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.db import Base, SessionLocal, engine
from app.core.seed import seed_defaults
from app.core.sqlite_migrate import ensure_sqlite_columns
from app import models  # noqa: F401 — 注册 ORM

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("zhishu")


def init_db() -> None:
    settings = get_settings()
    if settings.use_sqlite:
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_columns(engine)
        logger.info("sqlite ready: %s", settings.sqlite_path)
    else:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            Base.metadata.create_all(bind=conn)
        logger.info("postgres+pgvector ready")
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.files_path.mkdir(parents=True, exist_ok=True)
    init_db()
    from app.core.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
