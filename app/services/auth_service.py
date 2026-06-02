"""In-house OAuth 2.0 authentication."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.auth_utils import parse_user_id
from app.core.config import get_settings
from app.core.exceptions import (
    AccountPendingApprovalError,
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    safe_decode_token,
    verify_password,
)
from app.models.enums import UserRole, UserStatus
from app.models.oauth import OAuthRefreshToken
from app.models.user import User
from app.repositories.oauth import OAuthTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services.audit_service import AuditActions, AuditService

settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = OAuthTokenRepository(db)
        self.audit = AuditService(db)

    def login(self, email: str, password: str) -> TokenResponse:
        user = self.users.get_by_email(email.lower())
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        if user.status == UserStatus.pending:
            raise AccountPendingApprovalError()
        if user.status != UserStatus.active:
            raise ForbiddenError(
                "Your account is not active. Contact campus administration for assistance."
            )

        tokens = self._issue_tokens(user)
        self.audit.record(
            AuditActions.USER_LOGIN,
            "user",
            actor_user_id=user.id,
            entity_id=str(user.id),
            after={"role": user.role.value},
            commit=True,
        )
        return tokens

    def refresh(self, refresh_token: str) -> TokenResponse:
        payload = safe_decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")

        user_id = parse_user_id(payload.get("sub"))
        stored = self.tokens.get_by_hash(_hash_token(refresh_token))
        if not stored or stored.revoked_at:
            raise UnauthorizedError("Refresh token revoked")
        if stored.user_id != user_id:
            raise UnauthorizedError("Invalid refresh token")

        expires = stored.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            raise UnauthorizedError("Refresh token expired")

        user = self.users.get_by_id(user_id)
        if not user or user.status != UserStatus.active:
            raise UnauthorizedError("User not found")

        self.tokens.revoke(stored)
        return self._issue_tokens(user)

    def logout(self, refresh_token: str, *, current_user_id: UUID) -> None:
        stored = self.tokens.get_by_hash(_hash_token(refresh_token))
        if not stored:
            return
        if stored.user_id != current_user_id:
            raise ForbiddenError("Cannot revoke another user's session")
        self.tokens.revoke(stored)
        self.audit.record(
            AuditActions.USER_LOGOUT,
            "user",
            actor_user_id=current_user_id,
            entity_id=str(current_user_id),
            commit=True,
        )

    def self_register(
        self,
        *,
        email: str,
        password: str,
        role: UserRole,
        phone: str | None = None,
    ) -> User:
        normalized_email = email.lower()
        if self.users.get_by_email(normalized_email):
            raise ConflictError("Email already registered")
        if role == UserRole.admin:
            raise ForbiddenError("Admin role cannot be self-registered")
        if role not in (UserRole.student, UserRole.staff, UserRole.vendor):
            raise ForbiddenError("Role cannot be self-registered")

        user = User(
            email=normalized_email,
            phone=phone,
            hashed_password=hash_password(password),
            role=role,
            status=UserStatus.pending,
        )
        self.users.create(user)
        self.audit.record(
            AuditActions.USER_REGISTERED,
            "user",
            entity_id=str(user.id),
            after={"email": user.email, "role": user.role.value, "status": user.status.value},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def _issue_tokens(self, user: User) -> TokenResponse:
        access = create_access_token(str(user.id), role=user.role.value)
        refresh, expires = create_refresh_token(str(user.id))
        self.tokens.create(
            OAuthRefreshToken(
                user_id=user.id,
                token_hash=_hash_token(refresh),
                expires_at=expires,
            )
        )
        self.db.commit()
        return TokenResponse(
            access_token=access,
            expires_in=settings.access_token_expire_minutes * 60,
            refresh_token=refresh,
        )
