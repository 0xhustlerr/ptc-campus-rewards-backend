import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.earning_rule import EarningRule


class EarningRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, rule_id: uuid.UUID) -> EarningRule | None:
        return self.db.get(EarningRule, rule_id)

    def get_by_code(self, code: str) -> EarningRule | None:
        stmt = select(EarningRule).where(EarningRule.code == code)
        return self.db.scalars(stmt).first()

    def list_active(self) -> list[EarningRule]:
        stmt = select(EarningRule).where(EarningRule.active.is_(True))
        return list(self.db.scalars(stmt).all())

    def list_all(self) -> list[EarningRule]:
        return list(self.db.scalars(select(EarningRule)).all())

    def create(self, rule: EarningRule) -> EarningRule:
        self.db.add(rule)
        self.db.flush()
        return rule
