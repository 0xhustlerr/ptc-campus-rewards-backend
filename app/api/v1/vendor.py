"""Vendor QR scan and PTC Credits redemption."""

from fastapi import APIRouter, Request

from app.api.deps import DbSession, VendorUser
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.ledger import (
    RedemptionReceiptResponse,
    VendorRedeemRequest,
    VendorScanRequest,
    VendorScanResponse,
)
from app.services.redemption_service import RedemptionService

router = APIRouter()
settings = get_settings()


@router.post("/scan", response_model=VendorScanResponse)
@limiter.limit(settings.rate_limit_qr_scan)
def scan(request: Request, body: VendorScanRequest, db: DbSession, _: VendorUser) -> VendorScanResponse:
    result = RedemptionService(db).scan_session(body.qr_session_token)
    return VendorScanResponse(**result)


@router.post("/redeem", response_model=RedemptionReceiptResponse)
@limiter.limit(settings.rate_limit_redeem)
def redeem(
    request: Request,
    body: VendorRedeemRequest,
    db: DbSession,
    vendor: VendorUser,
) -> RedemptionReceiptResponse:
    receipt = RedemptionService(db).redeem(
        vendor_user_id=vendor.id,
        qr_session_token=body.qr_session_token,
        reward_item_id=body.reward_item_id,
        idempotency_key=body.idempotency_key,
    )
    return RedemptionReceiptResponse(**receipt)


@router.get("/redemptions", response_model=list[RedemptionReceiptResponse])
def vendor_redemptions(db: DbSession, vendor: VendorUser) -> list[RedemptionReceiptResponse]:
    receipts = RedemptionService(db).list_vendor_receipts(vendor.id)
    return [RedemptionReceiptResponse(**r) for r in receipts]
