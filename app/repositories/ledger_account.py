import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AccountType
from app.models.ledger_account import LedgerAccount


class LedgerAccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, account_id: uuid.UUID) -> LedgerAccount | None:
        return self.db.get(LedgerAccount, account_id)

    def get_student_wallet_account(self, wallet_id: uuid.UUID) -> LedgerAccount | None:
        stmt = select(LedgerAccount).where(
            LedgerAccount.wallet_id == wallet_id,
            LedgerAccount.account_type == AccountType.student_wallet,
        )
        return self.db.scalars(stmt).first()

    def lock_student_wallet_account(self, wallet_id: uuid.UUID) -> LedgerAccount | None:
        """Row lock for serializable balance updates during redeem/debit."""
        stmt = (
            select(LedgerAccount)
            .where(
                LedgerAccount.wallet_id == wallet_id,
                LedgerAccount.account_type == AccountType.student_wallet,
            )
            .with_for_update()
        )
        return self.db.scalars(stmt).first()

    def get_vendor_revenue_account(self, vendor_id: uuid.UUID) -> LedgerAccount | None:
        stmt = select(LedgerAccount).where(
            LedgerAccount.vendor_id == vendor_id,
            LedgerAccount.account_type == AccountType.vendor_revenue,
        )
        return self.db.scalars(stmt).first()

    def get_rewards_pool(self) -> LedgerAccount | None:
        stmt = select(LedgerAccount).where(
            LedgerAccount.account_type == AccountType.rewards_pool,
        )
        return self.db.scalars(stmt).first()

    def get_system_adjustment(self) -> LedgerAccount | None:
        stmt = select(LedgerAccount).where(
            LedgerAccount.account_type == AccountType.system_adjustment,
        )
        return self.db.scalars(stmt).first()

    def create(self, account: LedgerAccount) -> LedgerAccount:
        self.db.add(account)
        self.db.flush()
        return account
