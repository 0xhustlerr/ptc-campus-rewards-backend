"""Ledger transaction schemas exposed to clients."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.models.ledger import LedgerSource, TransactionType
from app.schemas.common import ORMModel


class TransactionRead(ORMModel):
    id: str
    user_id: str
    type: TransactionType
    amount: Decimal = Field(description="PTC Credits amount")
    description: str | None = None
    source: LedgerSource
    created_at: datetime


class ActivityTimelineItemRead(ORMModel):
    id: str
    title: str
    credits: Decimal
    earned_at: datetime
    category: str
