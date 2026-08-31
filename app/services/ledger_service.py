"""
Double-entry PTC Credits ledger.

Earn:  debit rewards_pool, credit student_wallet
Redeem: debit student_wallet, credit vendor_revenue
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    InsufficientCreditsError,
    LedgerError,
    NotFoundError,
)
from app.models.enums import (
    AccountType,
    EarningEventStatus,
    EntryDirection,
    RedemptionStatus,
    TransactionStatus,
    TransactionType,
    WalletStatus,
)
from app.models.ledger import LedgerEntry, LedgerTransaction
from app.models.ledger_account import LedgerAccount
from app.repositories.ledger import LedgerRepository
from app.repositories.ledger_account import LedgerAccountRepository
from app.repositories.reward_item import RewardItemRepository
from app.repositories.wallet import WalletRepository


@dataclass(frozen=True)
class EntrySpec:
    account_id: UUID
    direction: EntryDirection
    amount: Decimal


class LedgerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.ledger = LedgerRepository(db)
        self.accounts = LedgerAccountRepository(db)
        self.wallets = WalletRepository(db)
        self.items = RewardItemRepository(db)

    def get_by_idempotency_key(self, key: str) -> LedgerTransaction | None:
        return self.ledger.get_by_idempotency_key(key)

    def post_transaction(
        self,
        *,
        transaction_type: TransactionType,
        idempotency_key: str,
        entries: list[EntrySpec],
        created_by: UUID | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerTransaction:
        existing = self.ledger.get_by_idempotency_key(idempotency_key)
        if existing:
            # An idempotency key must never resolve to a transaction of a
            # different type. Without this guard a key harvested from one
            # operation (e.g. a student's own earn) could be replayed into a
            # redeem, which would then "complete" against the earn transaction
            # with no debit ever posted. Callers additionally scope keys by
            # actor, so a genuine retry always matches on type here.
            if existing.transaction_type != transaction_type:
                raise ConflictError(
                    "Idempotency key already used for a different transaction"
                )
            return existing

        if not entries:
            raise LedgerError("Transaction requires at least one ledger entry")

        for spec in entries:
            if spec.amount <= 0:
                raise LedgerError("Entry amounts must be positive")

        total_debits = sum(e.amount for e in entries if e.direction == EntryDirection.debit)
        total_credits = sum(e.amount for e in entries if e.direction == EntryDirection.credit)
        if total_debits != total_credits:
            raise LedgerError(
                f"Debits ({total_debits}) must equal credits ({total_credits})"
            )

        try:
            return self._insert_transaction(
                transaction_type=transaction_type,
                idempotency_key=idempotency_key,
                entries=entries,
                created_by=created_by,
                reference_type=reference_type,
                reference_id=reference_id,
                metadata=metadata,
            )
        except IntegrityError:
            # A concurrent post won the unique idempotency key. The transaction is
            # now aborted, so we must roll back — but that discards the caller's
            # own uncommitted rows (the earning event / redemption), so we cannot
            # safely return the raced transaction for the caller to attach to a
            # now-gone row. Raise a retryable conflict; callers dedupe idempotently
            # on retry via their own key checks.
            self.db.rollback()
            raise ConflictError("Concurrent transaction conflict; please retry")

    def _insert_transaction(
        self,
        *,
        transaction_type: TransactionType,
        idempotency_key: str,
        entries: list[EntrySpec],
        created_by: UUID | None,
        reference_type: str | None,
        reference_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> LedgerTransaction:
        tx = LedgerTransaction(
            transaction_type=transaction_type,
            status=TransactionStatus.pending,
            idempotency_key=idempotency_key,
            created_by=created_by,
            reference_type=reference_type,
            reference_id=reference_id,
            metadata_json=metadata,
        )
        self.ledger.add_transaction(tx)

        for spec in entries:
            self.ledger.add_entry(
                LedgerEntry(
                    transaction_id=tx.id,
                    account_id=spec.account_id,
                    direction=spec.direction,
                    amount=spec.amount,
                )
            )

        tx.status = TransactionStatus.posted
        self.db.flush()
        return tx

    def earn(
        self,
        *,
        wallet_id: UUID,
        amount: Decimal,
        idempotency_key: str,
        created_by: UUID | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerTransaction:
        wallet = self._require_active_wallet(wallet_id)
        student_account = self.accounts.get_student_wallet_account(wallet.id)
        pool_account = self.accounts.get_rewards_pool()
        if not student_account or not pool_account:
            raise NotFoundError("Ledger accounts not configured")

        return self.post_transaction(
            transaction_type=TransactionType.earn,
            idempotency_key=idempotency_key,
            created_by=created_by,
            reference_type=reference_type,
            reference_id=reference_id,
            metadata=metadata,
            entries=[
                EntrySpec(pool_account.id, EntryDirection.debit, amount),
                EntrySpec(student_account.id, EntryDirection.credit, amount),
            ],
        )

    def redeem(
        self,
        *,
        wallet_id: UUID,
        vendor_id: UUID,
        amount: Decimal,
        idempotency_key: str,
        created_by: UUID | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerTransaction:
        wallet = self._require_active_wallet(wallet_id)
        student_account = self._locked_student_account(wallet.id)
        vendor_account = self.accounts.get_vendor_revenue_account(vendor_id)
        if not student_account or not vendor_account:
            raise NotFoundError("Ledger accounts not found")

        balance = self.ledger.account_balance(student_account.id)
        if balance < amount:
            raise InsufficientCreditsError()

        return self.post_transaction(
            transaction_type=TransactionType.redeem,
            idempotency_key=idempotency_key,
            created_by=created_by,
            reference_type=reference_type,
            reference_id=reference_id,
            metadata=metadata,
            entries=[
                EntrySpec(student_account.id, EntryDirection.debit, amount),
                EntrySpec(vendor_account.id, EntryDirection.credit, amount),
            ],
        )

    def reverse_transaction(
        self,
        original_tx_id: UUID,
        *,
        idempotency_key: str,
        created_by: UUID | None = None,
    ) -> LedgerTransaction:
        # Idempotent replay: a retried reversal (same key, e.g. after a client
        # timeout on a request that actually committed) returns the original
        # result instead of tripping the already-reversed guard below.
        existing = self.ledger.get_by_idempotency_key(idempotency_key)
        if existing:
            if existing.transaction_type != TransactionType.reversal:
                raise ConflictError(
                    "Idempotency key already used for a different transaction"
                )
            return existing

        original = self.ledger.get_transaction_for_update(original_tx_id)
        if not original:
            raise NotFoundError("Original transaction not found")
        if original.status == TransactionStatus.reversed:
            raise LedgerError("Transaction already reversed")
        if original.status != TransactionStatus.posted:
            raise LedgerError("Only posted transactions can be reversed")

        reversed_entries = [
            EntrySpec(
                entry.account_id,
                EntryDirection.credit
                if entry.direction == EntryDirection.debit
                else EntryDirection.debit,
                entry.amount,
            )
            for entry in original.entries
        ]

        # A reversal must not drive a student wallet negative. Any student-wallet
        # entry that was a CREDIT in the original becomes a DEBIT here, so lock
        # that account and verify the balance covers it (e.g. reversing an earn
        # whose credits were already spent must be refused, not silently negative).
        for entry in original.entries:
            account = entry.account
            if (
                account is not None
                and account.account_type == AccountType.student_wallet
                and entry.direction == EntryDirection.credit
            ):
                self.accounts.lock_student_wallet_account(account.wallet_id)
                if self.ledger.account_balance(account.id) < entry.amount:
                    raise InsufficientCreditsError(
                        "Cannot reverse: student balance is insufficient "
                        "(credits already spent)"
                    )

        tx = self.post_transaction(
            transaction_type=TransactionType.reversal,
            idempotency_key=idempotency_key,
            created_by=created_by,
            reference_type="ledger_transaction",
            reference_id=str(original_tx_id),
            metadata={"reverses": str(original_tx_id)},
            entries=reversed_entries,
        )
        original.status = TransactionStatus.reversed

        # Cascade to the domain rows this transaction backed so reports, receipts,
        # and stock reflect the reversal.
        for event in original.earning_events:
            event.status = EarningEventStatus.reversed
        for redemption in original.redemptions:
            redemption.status = RedemptionStatus.reversed
            self.items.restore_inventory(redemption.reward_item_id)

        self.db.flush()
        return tx

    def adjustment(
        self,
        *,
        wallet_id: UUID,
        amount: Decimal,
        credit_student: bool,
        idempotency_key: str,
        created_by: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerTransaction:
        wallet = self._require_active_wallet(wallet_id)
        student_account = self._locked_student_account(wallet.id)
        system_account = self.accounts.get_system_adjustment()
        if not student_account or not system_account:
            raise NotFoundError("Ledger accounts not configured")

        if credit_student:
            entries = [
                EntrySpec(system_account.id, EntryDirection.debit, amount),
                EntrySpec(student_account.id, EntryDirection.credit, amount),
            ]
        else:
            balance = self.ledger.account_balance(student_account.id)
            if balance < amount:
                raise InsufficientCreditsError()
            entries = [
                EntrySpec(student_account.id, EntryDirection.debit, amount),
                EntrySpec(system_account.id, EntryDirection.credit, amount),
            ]

        return self.post_transaction(
            transaction_type=TransactionType.adjustment,
            idempotency_key=idempotency_key,
            created_by=created_by,
            reference_type="wallet",
            reference_id=str(wallet_id),
            metadata=metadata,
            entries=entries,
        )

    def _locked_student_account(self, wallet_id: UUID) -> LedgerAccount | None:
        return self.accounts.lock_student_wallet_account(wallet_id)

    def _require_active_wallet(self, wallet_id: UUID):
        wallet = self.wallets.get_by_id(wallet_id)
        if not wallet:
            raise NotFoundError("Wallet not found")
        if wallet.status != WalletStatus.active:
            raise LedgerError("Wallet is not active")
        return wallet

    def wallet_balance(self, wallet_id: UUID) -> Decimal:
        account = self.accounts.get_student_wallet_account(wallet_id)
        if not account:
            return Decimal("0")
        return self.ledger.account_balance(account.id)

    def list_wallet_transactions(self, wallet_id: UUID, *, limit: int, offset: int):
        return self.ledger.list_wallet_transactions(wallet_id, limit=limit, offset=offset)

    def count_wallet_transactions(self, wallet_id: UUID) -> int:
        return self.ledger.count_wallet_transactions(wallet_id)

    def list_all_transactions(self, limit: int = 200):
        return self.ledger.list_all_transactions(limit)
