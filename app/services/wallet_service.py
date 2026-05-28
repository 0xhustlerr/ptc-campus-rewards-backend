"""Wallet provisioning and balance reads."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import AccountType
from app.models.ledger_account import LedgerAccount
from app.models.wallet import DEFAULT_CURRENCY, Wallet, WalletStatus
from app.repositories.ledger import LedgerRepository
from app.repositories.ledger_account import LedgerAccountRepository
from app.repositories.student import StudentRepository
from app.repositories.wallet import WalletRepository
from app.services.ledger_service import LedgerService


class WalletService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallets = WalletRepository(db)
        self.students = StudentRepository(db)
        self.accounts = LedgerAccountRepository(db)
        self.ledger = LedgerRepository(db)
        self.ledger_svc = LedgerService(db)

    def create_wallet_for_student(self, student_id: UUID) -> Wallet:
        student = self.students.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student not found")
        if student.wallet:
            raise ConflictError("Student already has a wallet")

        wallet = Wallet(student_id=student_id, currency_code=DEFAULT_CURRENCY, status=WalletStatus.active)
        self.wallets.create(wallet)

        self.accounts.create(
            LedgerAccount(
                wallet_id=wallet.id,
                account_type=AccountType.student_wallet,
                name=f"PTC Wallet — {student.full_name}",
            )
        )
        self.db.flush()
        return wallet

    def get_balance(self, wallet_id: UUID) -> Decimal:
        account = self.accounts.get_student_wallet_account(wallet_id)
        if not account:
            raise NotFoundError("Wallet ledger account not found")
        return self.ledger.account_balance(account.id)

    def get_wallet_for_user(self, user_id: UUID) -> Wallet:
        student = self.students.get_by_user_id(user_id)
        if not student or not student.wallet:
            raise NotFoundError("Student wallet not found")
        return student.wallet

    def list_transactions(self, wallet_id: UUID, *, limit: int, offset: int):
        return self.ledger_svc.list_wallet_transactions(wallet_id, limit=limit, offset=offset)

    def count_transactions(self, wallet_id: UUID) -> int:
        return self.ledger_svc.count_wallet_transactions(wallet_id)
