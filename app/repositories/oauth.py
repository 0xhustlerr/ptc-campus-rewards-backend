from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.oauth import OAuthRefreshToken


class OAuthTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, token: OAuthRefreshToken) -> OAuthRefreshToken:
        self.db.add(token)
        self.db.flush()
        return token

    def get_by_hash(self, token_hash: str) -> OAuthRefreshToken | None:
        stmt = select(OAuthRefreshToken).where(OAuthRefreshToken.token_hash == token_hash)
        return self.db.scalars(stmt).first()

    def revoke(self, token: OAuthRefreshToken) -> None:
        token.revoked_at = datetime.now(UTC)

    def revoke_all_for_user(self, user_id: UUID) -> None:
        now = datetime.now(UTC)
        self.db.execute(
            update(OAuthRefreshToken)
            .where(
                OAuthRefreshToken.user_id == user_id,
                OAuthRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
