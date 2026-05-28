"""Celery background jobs for PTC Credits campus operations."""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.admin_metrics import AdminMetricsSnapshot
from app.models.earning_event import EarningEvent
from app.models.enums import EarningEventStatus, StudentStatus
from app.models.qr_session import QRSession
from app.repositories.earning_rule import EarningRuleRepository
from app.repositories.student import StudentRepository
from app.services.earning_service import EarningService
from app.services.reports_service import ReportsService
from app.services.system_accounts_service import SystemAccountsService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="app.workers.tasks.expire_old_qr_sessions")
def expire_old_qr_sessions() -> dict:
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        count = db.scalar(
            select(func.count())
            .select_from(QRSession)
            .where(QRSession.expires_at < now, QRSession.used_at.is_(None))
        )
        logger.info("Expired unused QR sessions: %s", count)
        return {"expired_unused_sessions": int(count or 0)}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.daily_token_activity_summary")
def daily_token_activity_summary() -> dict:
    db = SessionLocal()
    try:
        SystemAccountsService(db).ensure_system_accounts()
        summary = ReportsService(db).daily_activity_summary()
        db.add(
            AdminMetricsSnapshot(
                snapshot_type="daily_summary",
                snapshot_date=date.today(),
                data_json=summary,
            )
        )
        db.commit()
        return summary
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.generate_admin_metrics_snapshot")
def generate_admin_metrics_snapshot() -> dict:
    db = SessionLocal()
    try:
        svc = ReportsService(db)
        data = {
            "overview": svc.overview(),
            "token_velocity": svc.token_velocity(7),
            "earned_by_rule": svc.earned_by_rule(),
            "redeemed_by_category": svc.redeemed_by_category(),
            "top_students": svc.top_students(10),
            "vendor_summary": svc.vendor_summary(),
        }
        db.add(
            AdminMetricsSnapshot(
                snapshot_type="admin_overview",
                snapshot_date=date.today(),
                data_json=data,
            )
        )
        db.commit()
        return {"stored": True, "date": date.today().isoformat()}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.weekly_perfect_attendance_bonus")
def weekly_perfect_attendance_bonus() -> dict:
    db = SessionLocal()
    issued = 0
    skipped = 0
    try:
        SystemAccountsService(db).ensure_system_accounts()
        rules_repo = EarningRuleRepository(db)
        attendance_rule = rules_repo.get_by_code(settings.attendance_rule_code)
        bonus_rule = rules_repo.get_by_code(settings.perfect_attendance_rule_code)
        if not attendance_rule or not bonus_rule:
            return {"issued": 0, "error": "rules_missing"}

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        iso_year, iso_week, _ = today.isocalendar()
        required_days = settings.required_attendance_days_per_week

        week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=UTC)
        week_end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time()).replace(
            tzinfo=UTC
        )

        earning_svc = EarningService(db)
        for student in StudentRepository(db).list_all():
            if student.status != StudentStatus.active or not student.wallet:
                skipped += 1
                continue

            idempotency_key = f"perfect-attendance-{student.id}-{iso_year}-W{iso_week:02d}"
            if earning_svc.ledger.get_by_idempotency_key(idempotency_key):
                skipped += 1
                continue

            distinct_days = db.scalar(
                select(func.count(func.distinct(func.date(EarningEvent.created_at)))).where(
                    EarningEvent.student_id == student.id,
                    EarningEvent.rule_id == attendance_rule.id,
                    EarningEvent.status == EarningEventStatus.posted,
                    EarningEvent.created_at >= week_start_dt,
                    EarningEvent.created_at < week_end_dt,
                )
            )

            if int(distinct_days or 0) < required_days:
                skipped += 1
                continue

            earning_svc.issue_reward(
                student_id=student.id,
                earning_rule_id=bonus_rule.id,
                notes=f"Perfect attendance {iso_year}-W{iso_week:02d}",
                idempotency_key=idempotency_key,
                issued_by=student.user_id,
            )
            issued += 1

        return {"issued": issued, "skipped": skipped, "week": f"{iso_year}-W{iso_week:02d}"}
    finally:
        db.close()
