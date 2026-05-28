from decimal import Decimal

from pydantic import BaseModel, Field


class VendorDailySummaryRead(BaseModel):
    redemption_count: int
    total_credits_redeemed: Decimal = Field(description="Total PTC Credits redeemed today")
    top_item: str | None = None


class WalletScanRequest(BaseModel):
    session_token: str
