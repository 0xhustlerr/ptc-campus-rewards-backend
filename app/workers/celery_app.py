"""Celery application and beat schedule."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ptc_campus_rewards",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_default_queue="default",
    beat_schedule={
        "weekly-perfect-attendance": {
            "task": "app.workers.tasks.weekly_perfect_attendance_bonus",
            "schedule": crontab(hour=6, minute=0, day_of_week="monday"),
        },
        "daily-activity-summary": {
            "task": "app.workers.tasks.daily_token_activity_summary",
            "schedule": crontab(hour=23, minute=30),
        },
        "expire-qr-sessions": {
            "task": "app.workers.tasks.expire_old_qr_sessions",
            "schedule": crontab(minute="*/15"),
        },
        "admin-metrics-snapshot": {
            "task": "app.workers.tasks.generate_admin_metrics_snapshot",
            "schedule": crontab(hour=0, minute=5),
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
