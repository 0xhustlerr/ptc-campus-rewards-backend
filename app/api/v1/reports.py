"""Admin dashboard reports — PTC Credits program analytics."""

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbSession
from app.schemas.reports import (
    CategoryVolumeItem,
    ReportsOverviewResponse,
    RuleVolumeItem,
    TokenVelocityResponse,
    TopStudentItem,
    VendorSummaryItem,
)
from app.services.reports_service import ReportsService

router = APIRouter()


@router.get("/overview", response_model=ReportsOverviewResponse)
def reports_overview(db: DbSession, _: AdminUser) -> ReportsOverviewResponse:
    return ReportsOverviewResponse(**ReportsService(db).overview())


@router.get("/token-velocity", response_model=TokenVelocityResponse)
def token_velocity(
    db: DbSession,
    _: AdminUser,
    days: int = Query(7, ge=1, le=90),
) -> TokenVelocityResponse:
    return TokenVelocityResponse(**ReportsService(db).token_velocity(days))


@router.get("/earned-by-rule", response_model=list[RuleVolumeItem])
def earned_by_rule(db: DbSession, _: AdminUser) -> list[RuleVolumeItem]:
    return [RuleVolumeItem(**r) for r in ReportsService(db).earned_by_rule()]


@router.get("/redeemed-by-category", response_model=list[CategoryVolumeItem])
def redeemed_by_category(db: DbSession, _: AdminUser) -> list[CategoryVolumeItem]:
    return [CategoryVolumeItem(**r) for r in ReportsService(db).redeemed_by_category()]


@router.get("/top-students", response_model=list[TopStudentItem])
def top_students(
    db: DbSession,
    _: AdminUser,
    limit: int = Query(10, ge=1, le=50),
) -> list[TopStudentItem]:
    return [TopStudentItem(**r) for r in ReportsService(db).top_students(limit)]


@router.get("/vendor-summary", response_model=list[VendorSummaryItem])
def vendor_summary(db: DbSession, _: AdminUser) -> list[VendorSummaryItem]:
    return [VendorSummaryItem(**r) for r in ReportsService(db).vendor_summary()]
