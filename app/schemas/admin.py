from datetime import datetime
from uuid import UUID

from app.models.enums import WalletStatus
from pydantic import BaseModel

from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict | None = None
    after: dict | None = None
    created_at: datetime


class WalletStatusUpdate(BaseModel):
    status: WalletStatus
