"""Admin operations — wallet status, ledger adjustments, audit logs."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import WalletStatus
from app.models.redemption import Redemption
from app.models.wallet import Wallet
from app.repositories.audit_log import AuditLogRepository
from app.repositories.redemption import RedemptionRepository
from app.repositories.user import UserRepository
from app.schemas.ledger import AdminAdjustmentRequest, AdminReversalRequest
from app.services.audit_service import AuditActions, AuditService
from app.services.ledger_service import LedgerService
from app.services.wallet_service import WalletService


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallets = WalletService(db)
        self.ledger = LedgerService(db)
        self.audit = AuditService(db)
        self.audit_logs = AuditLogRepository(db)
        self.redemptions = RedemptionRepository(db)
        self.users = UserRepository(db)

    def update_wallet_status(
        self, wallet_id: UUID, status: WalletStatus, *, actor_id: UUID
    ) -> Wallet:
        wallet = self.wallets.wallets.get_by_id(wallet_id)
        if not wallet:
            raise NotFoundError("Wallet not found")
        before = wallet.status.value
        wallet.status = status
        # Log the action that matches the target status rather than a binary
        # frozen/unfrozen, so "closed" isn't recorded as "unfrozen".
        action = {
            WalletStatus.frozen: AuditActions.WALLET_FROZEN,
            WalletStatus.closed: AuditActions.WALLET_CLOSED,
            WalletStatus.active: AuditActions.WALLET_ACTIVATED,
        }.get(status, AuditActions.WALLET_UNFROZEN)
        self.audit.record(
            action,
            "wallet",
            actor_user_id=actor_id,
            entity_id=str(wallet_id),
            before={"status": before},
            after={"status": status.value},
            commit=True,
        )
        self.db.refresh(wallet)
        return wallet

    def apply_adjustment(self, body: AdminAdjustmentRequest, *, actor_id: UUID):
        tx = self.ledger.adjustment(
            wallet_id=body.wallet_id,
            amount=body.amount,
            credit_student=body.credit_student,
            idempotency_key=body.idempotency_key,
            created_by=actor_id,
            metadata={"reason": body.reason},
        )
        self.audit.record(
            AuditActions.ADMIN_ADJUSTMENT,
            "ledger_transaction",
            actor_user_id=actor_id,
            entity_id=str(tx.id),
            after={"amount": str(body.amount), "credit_student": body.credit_student},
            commit=True,
        )
        return tx

    def apply_reversal(self, body: AdminReversalRequest, *, actor_id: UUID):
        tx = self.ledger.reverse_transaction(
            body.ledger_transaction_id,
            idempotency_key=body.idempotency_key,
            created_by=actor_id,
        )
        self.audit.record(
            AuditActions.TRANSACTION_REVERSAL,
            "ledger_transaction",
            actor_user_id=actor_id,
            entity_id=str(tx.id),
            after={"reverses": str(body.ledger_transaction_id)},
            commit=True,
        )
        return tx

    def list_audit_logs(self, limit: int) -> list:
        return self.audit_logs.list_recent(limit)

    def list_redemptions(self, limit: int = 200) -> list[Redemption]:
        return self.redemptions.list_all(limit)

    def resolve_actor_emails(self, actor_ids: list[UUID]) -> dict[UUID, str]:
        """Map distinct actor user ids to emails for human-readable audit logs."""
        emails: dict[UUID, str] = {}
        for actor_id in set(actor_ids):
            user = self.users.get_by_id(actor_id)
            if user:
                emails[actor_id] = user.email
        return emails
