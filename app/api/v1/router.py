"""Aggregate all v1 route modules."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, earning_rules, reports, rewards, staff, students, vendor, wallets
from app.core.config import get_settings
from app.schemas.common import HealthDetailResponse, HealthResponse

settings = get_settings()
api_router = APIRouter()


@api_router.get("/health", response_model=HealthResponse, tags=["health"])
def health_v1() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@api_router.get("/health/detail", response_model=HealthDetailResponse, tags=["health"])
def health_v1_detail() -> HealthDetailResponse:
    from app.utils.health import check_database, check_redis

    db_status = check_database()
    redis_status = check_redis()
    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthDetailResponse(
        status=overall,
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=db_status,
        redis=redis_status,
    )


api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(students.router, prefix="/students", tags=["students"])
api_router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
api_router.include_router(earning_rules.router, prefix="/earning-rules", tags=["earning-rules"])
api_router.include_router(rewards.router, prefix="/rewards", tags=["rewards"])
api_router.include_router(staff.router, prefix="/staff", tags=["staff"])
api_router.include_router(vendor.router, prefix="/vendor", tags=["vendor"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(reports.router, prefix="/admin/reports", tags=["reports"])
