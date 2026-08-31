from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class EarningRuleRead(ORMModel):
    id: UUID
    code: str
    name: str
    token_amount: Decimal = Field(description="PTC Credits per issuance")
    daily_limit: int | None
    weekly_limit: int | None
    requires_note: bool
    requires_approval: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class EarningRuleCreate(BaseModel):
    code: str
    name: str
    token_amount: Decimal = Field(gt=0, description="PTC Credits per issuance; must be positive")
    daily_limit: int | None = Field(default=None, ge=1)
    weekly_limit: int | None = Field(default=None, ge=1)
    requires_note: bool = False
    requires_approval: bool = False
    active: bool = True


class EarningRuleUpdate(BaseModel):
    name: str | None = None
    token_amount: Decimal | None = Field(default=None, gt=0)
    daily_limit: int | None = Field(default=None, ge=1)
    weekly_limit: int | None = Field(default=None, ge=1)
    requires_note: bool | None = None
    requires_approval: bool | None = None
    active: bool | None = None
