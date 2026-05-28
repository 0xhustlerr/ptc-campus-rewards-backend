"""Shared schema types."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str
    environment: str


class HealthDetailResponse(HealthResponse):
    database: str
    redis: str


class MessageResponse(BaseModel):
    message: str


class CreditsAmount(BaseModel):
    """PTC Credits amount — closed-loop campus currency, not a public token."""

    amount: Decimal = Field(..., ge=0, decimal_places=4)


class Timestamped(ORMModel):
    created_at: datetime
    updated_at: datetime | None = None
