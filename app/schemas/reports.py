from decimal import Decimal

from pydantic import BaseModel, Field


class ReportsOverviewResponse(BaseModel):
    total_students: int
    active_wallets: int
    total_ptc_issued: Decimal = Field(description="Total PTC Credits issued")
    total_ptc_redeemed: Decimal
    outstanding_ptc_balance: Decimal
    redemptions_today: int
    transactions_today: int
    most_active_student: str | None = None


class TokenVelocityDay(BaseModel):
    date: str
    issued: str
    redeemed: str
    transaction_count: int


class TokenVelocityResponse(BaseModel):
    days: int
    series: list[TokenVelocityDay]


class RuleVolumeItem(BaseModel):
    rule: str
    total_ptc: str
    event_count: int


class CategoryVolumeItem(BaseModel):
    category: str
    total_ptc: str
    redemption_count: int


class TopStudentItem(BaseModel):
    student_name: str
    balance: str
    transaction_count: int


class VendorSummaryItem(BaseModel):
    vendor_id: str
    vendor_name: str
    vendor_type: str
    total_ptc_redeemed: str
    redemption_count: int
