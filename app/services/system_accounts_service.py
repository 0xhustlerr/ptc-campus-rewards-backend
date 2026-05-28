"""Ensure system-level ledger accounts exist (rewards pool, adjustments)."""

from sqlalchemy.orm import Session

from app.models.enums import AccountType
from app.models.ledger_account import LedgerAccount
from app.repositories.ledger_account import LedgerAccountRepository

REWARDS_POOL_NAME = "PTC Campus Rewards Pool"
SYSTEM_ADJUSTMENT_NAME = "PTC System Adjustments"


class SystemAccountsService:
    def __init__(self, db: Session) -> None:
        self.accounts = LedgerAccountRepository(db)
        self.db = db

    def ensure_system_accounts(self) -> tuple[LedgerAccount, LedgerAccount]:
        pool = self.accounts.get_rewards_pool()
        if not pool:
            pool = LedgerAccount(
                account_type=AccountType.rewards_pool,
                name=REWARDS_POOL_NAME,
            )
            self.accounts.create(pool)

        adjustment = self.accounts.get_system_adjustment()
        if not adjustment:
            adjustment = LedgerAccount(
                account_type=AccountType.system_adjustment,
                name=SYSTEM_ADJUSTMENT_NAME,
            )
            self.accounts.create(adjustment)

        self.db.flush()
        return pool, adjustment

    def ensure_vendor_account(self, vendor_id, vendor_name: str) -> LedgerAccount:
        account = self.accounts.get_vendor_revenue_account(vendor_id)
        if account:
            return account
        account = LedgerAccount(
            vendor_id=vendor_id,
            account_type=AccountType.vendor_revenue,
            name=f"Vendor Revenue — {vendor_name}",
        )
        self.accounts.create(account)
        self.db.flush()
        return account
