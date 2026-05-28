"""Admin catalog operations for earning rules and reward items."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.earning_rule import EarningRule
from app.models.reward_item import RewardItem
from app.repositories.earning_rule import EarningRuleRepository
from app.repositories.reward_item import RewardItemRepository
from app.schemas.earning_rule import EarningRuleCreate, EarningRuleUpdate
from app.schemas.reward import RewardItemCreate, RewardItemUpdate
from app.services.audit_service import AuditActions, AuditService


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rules = EarningRuleRepository(db)
        self.items = RewardItemRepository(db)
        self.audit = AuditService(db)

    def create_earning_rule(self, data: EarningRuleCreate, *, actor_id: UUID) -> EarningRule:
        rule = EarningRule(**data.model_dump())
        self.rules.create(rule)
        self.audit.record(
            AuditActions.EARNING_RULE_CREATED,
            "earning_rule",
            actor_user_id=actor_id,
            entity_id=str(rule.id),
            after=data.model_dump(mode="json"),
            commit=True,
        )
        self.db.refresh(rule)
        return rule

    def update_earning_rule(
        self, rule_id: UUID, data: EarningRuleUpdate, *, actor_id: UUID
    ) -> EarningRule:
        rule = self.rules.get_by_id(rule_id)
        if not rule:
            raise NotFoundError("Earning rule not found")
        before = {"name": rule.name, "token_amount": str(rule.token_amount), "active": rule.active}
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        self.audit.record(
            AuditActions.EARNING_RULE_UPDATED,
            "earning_rule",
            actor_user_id=actor_id,
            entity_id=str(rule_id),
            before=before,
            after=data.model_dump(exclude_unset=True, mode="json"),
            commit=True,
        )
        self.db.refresh(rule)
        return rule

    def create_reward_item(self, data: RewardItemCreate, *, actor_id: UUID) -> RewardItem:
        item = RewardItem(**data.model_dump())
        self.items.create(item)
        self.audit.record(
            AuditActions.REWARD_ITEM_CREATED,
            "reward_item",
            actor_user_id=actor_id,
            entity_id=str(item.id),
            after=data.model_dump(mode="json"),
            commit=True,
        )
        self.db.refresh(item)
        return item

    def update_reward_item(
        self, item_id: UUID, data: RewardItemUpdate, *, actor_id: UUID
    ) -> RewardItem:
        item = self.items.get_by_id(item_id)
        if not item:
            raise NotFoundError("Reward item not found")
        before = {"name": item.name, "price_tokens": str(item.price_tokens), "active": item.active}
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        self.audit.record(
            AuditActions.REWARD_ITEM_UPDATED,
            "reward_item",
            actor_user_id=actor_id,
            entity_id=str(item_id),
            before=before,
            after=data.model_dump(exclude_unset=True, mode="json"),
            commit=True,
        )
        self.db.refresh(item)
        return item
