"""Public earning rules catalog."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.repositories.earning_rule import EarningRuleRepository
from app.schemas.earning_rule import EarningRuleRead
from app.utils.mappers import earning_rule_to_read

router = APIRouter()


@router.get("", response_model=list[EarningRuleRead])
def list_earning_rules(db: DbSession, _: CurrentUser) -> list[EarningRuleRead]:
    return [earning_rule_to_read(r) for r in EarningRuleRepository(db).list_active()]
