"""进程内 stub 调度（无 Redis/Celery 时兜底 C-002/C-104）。

- 退休扫描：按间隔执行
- 夜间评测：本地时区到达配置小时且当日未跑则执行
正式环境可改用 Celery beat（worker/celery_app.beat_schedule）。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.jobs import get_job_status, run_nightly_eval_all, run_retire_scan_all

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None
_state: dict = {
    "enabled": False,
    "mode": "off",
    "last_retire_date": None,
    "last_eval_date": None,
    "tick": 0,
}


def get_scheduler_state() -> dict:
    settings = get_settings()
    return {
        **_state,
        "jobs": get_job_status(),
        "config": {
            "scheduler_enabled": settings.scheduler_enabled,
            "retire_interval_hours": settings.retire_scan_interval_hours,
            "eval_nightly_hour": settings.eval_nightly_hour,
            "scheduler_timezone": settings.scheduler_timezone,
            "stub_fast": settings.scheduler_stub_fast,
        },
    }


def start_scheduler() -> None:
    global _thread
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("scheduler disabled")
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _state["enabled"] = True
    _state["mode"] = "stub_thread" if settings.zhishu_dev_stub else "stub_thread"
    _thread = threading.Thread(target=_loop, name="zhishu-scheduler", daemon=True)
    _thread.start()
    logger.info(
        "scheduler started tz=%s retire_h=%s eval_hour=%s fast=%s",
        settings.scheduler_timezone,
        settings.retire_scan_interval_hours,
        settings.eval_nightly_hour,
        settings.scheduler_stub_fast,
    )


def stop_scheduler() -> None:
    _stop.set()
    _state["enabled"] = False
    logger.info("scheduler stop signaled")


def _loop() -> None:
    settings = get_settings()
    # stub_fast：更快验证（退休 2 分钟、评测按小时窗口 + 启动后可立即补跑）
    retire_sec = (
        120.0
        if settings.scheduler_stub_fast
        else max(300.0, settings.retire_scan_interval_hours * 3600.0)
    )
    last_retire = 0.0
    # 启动后稍等，避免与 create_all/seed 抢锁
    if _stop.wait(8.0):
        return
    while not _stop.is_set():
        _state["tick"] = int(_state.get("tick") or 0) + 1
        now_mono = time.monotonic()
        try:
            if now_mono - last_retire >= retire_sec:
                run_retire_scan_all()
                last_retire = now_mono
                _state["last_retire_date"] = date.today().isoformat()
        except Exception:  # noqa: BLE001
            logger.exception("scheduler retire tick failed")

        try:
            _maybe_nightly_eval()
        except Exception:  # noqa: BLE001
            logger.exception("scheduler eval tick failed")

        if _stop.wait(30.0):
            break


def _maybe_nightly_eval() -> None:
    settings = get_settings()
    try:
        now = datetime.now(ZoneInfo(settings.scheduler_timezone))
    except Exception:  # noqa: BLE001 — Windows 缺 tzdata 时回退本地时区
        now = datetime.now().astimezone()
    today = now.date().isoformat()
    if _state.get("last_eval_date") == today:
        return
    # stub_fast：启动后当日跑一次子集；正式：到达配置小时
    if settings.scheduler_stub_fast:
        run_nightly_eval_all(limit=5)
        _state["last_eval_date"] = today
        return
    if now.hour == settings.eval_nightly_hour:
        run_nightly_eval_all()
        _state["last_eval_date"] = today
