from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import RewardCategory, RedemptionStatus
from app.schemas.common import ORMModel


class RewardItemRead(ORMModel):
    id: UUID
    vendor_id: UUID | None
    name: str
    category: RewardCategory
    price_tokens: Decimal = Field(description="PTC Credits required")
    inventory_count: int | None
    active: bool
    created_at: datetime
    updated_at: datetime


class RewardItemCreate(BaseModel):
    name: str
    category: RewardCategory
    price_tokens: Decimal = Field(gt=0, description="PTC Credits required; must be positive")
    vendor_id: UUID | None = None
    inventory_count: int | None = Field(default=None, ge=0)
    active: bool = True


class RewardItemUpdate(BaseModel):
    name: str | None = None
    category: RewardCategory | None = None
    price_tokens: Decimal | None = Field(default=None, gt=0)
    inventory_count: int | None = Field(default=None, ge=0)
    active: bool | None = None
    vendor_id: UUID | None = None


class RedemptionRead(ORMModel):
    id: UUID
    student_id: UUID
    vendor_id: UUID
    reward_item_id: UUID
    amount_tokens: Decimal
    status: RedemptionStatus
    failure_reason: str | None
    created_at: datetime
