"""Ensure system-level ledger accounts exist (rewards pool, adjustments)."""

from sqlalchemy.exc import IntegrityError
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
        pool = self._get_or_create(
            self.accounts.get_rewards_pool,
            lambda: LedgerAccount(account_type=AccountType.rewards_pool, name=REWARDS_POOL_NAME),
        )
        adjustment = self._get_or_create(
            self.accounts.get_system_adjustment,
            lambda: LedgerAccount(
                account_type=AccountType.system_adjustment, name=SYSTEM_ADJUSTMENT_NAME
            ),
        )
        return pool, adjustment

    def ensure_vendor_account(self, vendor_id, vendor_name: str) -> LedgerAccount:
        return self._get_or_create(
            lambda: self.accounts.get_vendor_revenue_account(vendor_id),
            lambda: LedgerAccount(
                vendor_id=vendor_id,
                account_type=AccountType.vendor_revenue,
                name=f"Vendor Revenue — {vendor_name}",
            ),
        )

    def _get_or_create(self, getter, factory) -> LedgerAccount:
        """Idempotent ensure: if a concurrent creator wins the race, the unique
        index (migration 009) rejects our insert and we return the existing row
        instead of splitting balances across duplicate accounts."""
        existing = getter()
        if existing:
            return existing
        account = factory()
        self.accounts.create(account)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = getter()
            if existing:
                return existing
            raise
        return account
