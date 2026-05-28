"""Reward catalog for students and vendors."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.repositories.reward_item import RewardItemRepository
from app.schemas.reward import RewardItemRead
from app.utils.mappers import reward_item_to_read

router = APIRouter()


@router.get("/catalog", response_model=list[RewardItemRead])
def catalog(db: DbSession, _: CurrentUser) -> list[RewardItemRead]:
    return [reward_item_to_read(i) for i in RewardItemRepository(db).list_active()]
