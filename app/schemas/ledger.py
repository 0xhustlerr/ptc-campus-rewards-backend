from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import EntryDirection, TransactionStatus, TransactionType
from app.schemas.common import ORMModel


class LedgerEntryRead(ORMModel):
    id: UUID
    account_id: UUID
    direction: EntryDirection
    amount: Decimal
    created_at: datetime


class LedgerTransactionRead(ORMModel):
    id: UUID
    transaction_type: TransactionType
    status: TransactionStatus
    reference_type: str | None
    reference_id: str | None
    idempotency_key: str
    amount: Decimal = Field(description="PTC Credits moved")
    created_at: datetime
    entries: list[LedgerEntryRead] = []


class IssueRewardRequest(BaseModel):
    student_id: UUID
    earning_rule_id: UUID
    notes: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)


class IssueRewardResponse(BaseModel):
    earning_event_id: UUID
    ledger_transaction_id: UUID | None
    amount: Decimal
    new_balance: Decimal
    status: str


class VendorScanRequest(BaseModel):
    qr_session_token: str


class VendorScanResponse(BaseModel):
    session_valid: bool
    student_display_name: str | None = None
    wallet_status: str | None = None
    balance: Decimal | None = None
    expires_at: str | None = None
    reason: str | None = None


class VendorRedeemRequest(BaseModel):
    qr_session_token: str
    reward_item_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)


class RedemptionReceiptResponse(BaseModel):
    redemption_id: str
    student_display_name: str
    item_name: str
    amount: Decimal = Field(description="PTC Credits redeemed")
    balance_before: Decimal
    balance_after: Decimal
    vendor_name: str
    redeemed_at: str


class QRSessionResponse(BaseModel):
    qr_session_token: str = Field(description="Opaque token to encode in QR — not the student ID")
    expires_at: str
    ttl_seconds: int


class AdminAdjustmentRequest(BaseModel):
    wallet_id: UUID
    amount: Decimal = Field(gt=0)
    credit_student: bool = Field(description="True to add PTC Credits, false to deduct")
    idempotency_key: str
    reason: str | None = None


class AdminReversalRequest(BaseModel):
    ledger_transaction_id: UUID
    idempotency_key: str
    reason: str | None = None
