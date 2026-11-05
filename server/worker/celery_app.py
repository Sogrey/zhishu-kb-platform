from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "zhishu",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["worker.tasks"],
)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        # C-002：每日 01:30 退休扫描
        "retire-scan-daily": {
            "task": "retire_scan_all",
            "schedule": crontab(hour=1, minute=30),
        },
        # C-104：每日 02:00 金标夜间回归
        "nightly-eval": {
            "task": "nightly_eval",
            "schedule": crontab(hour=settings.eval_nightly_hour, minute=0),
        },
    },
)
