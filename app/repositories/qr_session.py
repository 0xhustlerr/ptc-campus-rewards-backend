from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.qr_session import QRSession


class QRSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_token_hash(self, token_hash: str) -> QRSession | None:
        stmt = select(QRSession).where(QRSession.token_hash == token_hash)
        return self.db.scalars(stmt).first()

    def get_by_token_hash_for_update(self, token_hash: str) -> QRSession | None:
        stmt = select(QRSession).where(QRSession.token_hash == token_hash).with_for_update()
        return self.db.scalars(stmt).first()

    def create(self, session: QRSession) -> QRSession:
        self.db.add(session)
        self.db.flush()
        return session

    def mark_used_atomic(self, session_id: UUID) -> bool:
        """Returns True if this call consumed the session (exactly-once)."""
        result = self.db.execute(
            update(QRSession)
            .where(QRSession.id == session_id, QRSession.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
        )
        return result.rowcount == 1
