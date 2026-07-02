"""Immutable audit trail for PTC Credits operations."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.audit_log import AuditLogRepository


class AuditActions:
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_REGISTERED = "user.registered"
    ADMIN_CREATED = "admin.created"
    ADMIN_BOOTSTRAPPED = "admin.bootstrapped"
    USER_APPROVED = "user.approved"
    USER_REJECTED = "user.rejected"
    USER_STATUS_CHANGED = "user.status_changed"
    REWARD_ISSUED = "reward.issued"
    REWARD_APPROVED = "reward.approved"
    REWARD_REJECTED = "reward.rejected"
    REDEMPTION_COMPLETED = "redemption.completed"
    ADMIN_ADJUSTMENT = "admin.adjustment"
    TRANSACTION_REVERSAL = "transaction.reversal"
    EARNING_RULE_CREATED = "earning_rule.created"
    EARNING_RULE_UPDATED = "earning_rule.updated"
    REWARD_ITEM_CREATED = "reward_item.created"
    REWARD_ITEM_UPDATED = "reward_item.updated"
    WALLET_FROZEN = "wallet.frozen"
    WALLET_UNFROZEN = "wallet.unfrozen"
    WEEKLY_BONUS_ISSUED = "weekly_bonus.issued"


class AuditService:
    def __init__(self, db: Session) -> None:
        self.logs = AuditLogRepository(db)
        self.db = db

    def record(
        self,
        action: str,
        entity_type: str,
        *,
        actor_user_id: uuid.UUID | None = None,
        entity_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> AuditLog:
        log = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=before,
            after_json=after,
        )
        self.logs.create(log)
        if commit:
            self.db.commit()
        return log
