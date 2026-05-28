from datetime import UTC, datetime

from sqlalchemy import select
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
