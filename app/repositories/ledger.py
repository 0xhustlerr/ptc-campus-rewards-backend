"""Ledger transaction and entry data access."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import EntryDirection, TransactionStatus
from app.models.ledger import LedgerEntry, LedgerTransaction
from app.models.ledger_account import LedgerAccount


class LedgerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_idempotency_key(self, key: str) -> LedgerTransaction | None:
        stmt = (
            select(LedgerTransaction)
            .options(joinedload(LedgerTransaction.entries))
            .where(LedgerTransaction.idempotency_key == key)
        )
        return self.db.execute(stmt).unique().scalars().first()

    def get_transaction(self, tx_id: uuid.UUID) -> LedgerTransaction | None:
        stmt = (
            select(LedgerTransaction)
            .options(joinedload(LedgerTransaction.entries))
            .where(LedgerTransaction.id == tx_id)
        )
        return self.db.execute(stmt).unique().scalars().first()

    def get_transaction_for_update(self, tx_id: uuid.UUID) -> LedgerTransaction | None:
        # Lock only the transaction row. joinedload(entries) emits a LEFT OUTER
        # JOIN, and Postgres rejects an unqualified FOR UPDATE on the nullable
        # side of an outer join ("FOR UPDATE cannot be applied to the nullable
        # side of an outer join"). Scope the lock with of=LedgerTransaction so
        # only the base row is locked; entries are append-only and need no lock.
        stmt = (
            select(LedgerTransaction)
            .options(joinedload(LedgerTransaction.entries))
            .where(LedgerTransaction.id == tx_id)
            .with_for_update(of=LedgerTransaction)
        )
        return self.db.execute(stmt).unique().scalars().first()

    def add_transaction(self, tx: LedgerTransaction) -> LedgerTransaction:
        self.db.add(tx)
        self.db.flush()
        return tx

    def add_entry(self, entry: LedgerEntry) -> LedgerEntry:
        self.db.add(entry)
        self.db.flush()
        return entry

    def account_balance(self, account_id: uuid.UUID) -> Decimal:
        """Student wallet balance = credits - debits on posted transactions."""
        credit_sum = self._sum_direction(account_id, EntryDirection.credit)
        debit_sum = self._sum_direction(account_id, EntryDirection.debit)
        return credit_sum - debit_sum

    def _sum_direction(self, account_id: uuid.UUID, direction: EntryDirection) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(LedgerEntry.amount), 0))
            .join(LedgerTransaction)
            .where(
                LedgerEntry.account_id == account_id,
                LedgerEntry.direction == direction,
                LedgerTransaction.status.in_(
                    [TransactionStatus.posted, TransactionStatus.reversed]
                ),
            )
        )
        result = self.db.scalar(stmt)
        return Decimal(str(result or 0))

    def list_wallet_transactions(
        self,
        wallet_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LedgerTransaction]:
        account_ids = select(LedgerAccount.id).where(LedgerAccount.wallet_id == wallet_id)
        stmt = (
            select(LedgerTransaction)
            .join(LedgerEntry)
            .where(LedgerEntry.account_id.in_(account_ids))
            .options(joinedload(LedgerTransaction.entries))
            .order_by(LedgerTransaction.created_at.desc())
            .distinct()
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def wallet_totals(self, wallet_id: uuid.UUID) -> tuple[Decimal, Decimal]:
        """Lifetime (total_earned, total_redeemed) for a wallet, over all posted
        transactions — not just one page. Earned = credits from earn/bonus;
        redeemed = debits from redeem. Reversed originals fall out (status filter)."""
        from app.models.enums import TransactionType

        account_ids = select(LedgerAccount.id).where(LedgerAccount.wallet_id == wallet_id)
        rows = self.db.execute(
            select(
                LedgerTransaction.transaction_type,
                LedgerEntry.direction,
                func.coalesce(func.sum(LedgerEntry.amount), 0),
            )
            .join(LedgerTransaction, LedgerEntry.transaction_id == LedgerTransaction.id)
            .where(
                LedgerEntry.account_id.in_(account_ids),
                LedgerTransaction.status == TransactionStatus.posted,
            )
            .group_by(LedgerTransaction.transaction_type, LedgerEntry.direction)
        ).all()

        earned = Decimal("0")
        redeemed = Decimal("0")
        for tx_type, direction, total in rows:
            amount = Decimal(str(total or 0))
            if direction == EntryDirection.credit and tx_type in (
                TransactionType.earn,
                TransactionType.bonus,
            ):
                earned += amount
            elif direction == EntryDirection.debit and tx_type == TransactionType.redeem:
                redeemed += amount
        return earned, redeemed

    def count_wallet_transactions(self, wallet_id: uuid.UUID) -> int:
        account_ids = select(LedgerAccount.id).where(LedgerAccount.wallet_id == wallet_id)
        stmt = (
            select(func.count(func.distinct(LedgerTransaction.id)))
            .join(LedgerEntry)
            .where(LedgerEntry.account_id.in_(account_ids))
        )
        return int(self.db.scalar(stmt) or 0)

    def list_all_transactions(self, limit: int = 200) -> list[LedgerTransaction]:
        stmt = (
            select(LedgerTransaction)
            .options(joinedload(LedgerTransaction.entries))
            .order_by(LedgerTransaction.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).unique().scalars().all())
