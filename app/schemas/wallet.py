from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import WalletStatus
from app.schemas.common import ORMModel


class WalletRead(ORMModel):
    id: UUID
    student_id: UUID
    currency_code: str
    status: WalletStatus
    created_at: datetime
    updated_at: datetime


class WalletBalanceRead(BaseModel):
    wallet_id: UUID
    currency_code: str = Field(default="PTC", description="Campus currency code")
    balance: Decimal = Field(description="Computed PTC Credits balance from ledger entries")
    status: WalletStatus


class WalletMeRead(WalletBalanceRead):
    student_id: UUID
    student_name: str
    student_number: str


class WalletStatusUpdate(BaseModel):
    status: WalletStatus
