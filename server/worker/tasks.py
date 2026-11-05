import logging

from app.core.db import SessionLocal
from app.core.jobs import run_nightly_eval_all, run_retire_scan_all
from app.rag.ingest import run_ingest
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ingest_document", bind=True, max_retries=2)
def ingest_document(self, document_id: int) -> dict:
    db = SessionLocal()
    try:
        run_ingest(db, document_id)
        return {"document_id": document_id, "status": "ready"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("task ingest failed")
        raise self.retry(exc=exc, countdown=5) from exc
    finally:
        db.close()


@celery_app.task(name="retire_scan_all")
def retire_scan_all() -> dict:
    return run_retire_scan_all()


@celery_app.task(name="nightly_eval")
def nightly_eval() -> dict:
    return run_nightly_eval_all()
