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
from app.models.enums import UserRole, UserStatus, VendorType
from app.models.oauth import OAuthRefreshToken
from app.models.user import User
from app.repositories.oauth import OAuthTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services.audit_service import AuditActions, AuditService
from app.services.student_service import StudentService
from app.services.user_admin_service import UserAdminService

settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# Precomputed bcrypt hash used to equalize timing when an email does not exist,
# so login latency cannot be used to enumerate valid accounts.
_DUMMY_PASSWORD_HASH = hash_password("timing-attack-mitigation-placeholder")


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = OAuthTokenRepository(db)
        self.audit = AuditService(db)

    def login(self, email: str, password: str) -> TokenResponse:
        user = self.users.get_by_email(email.lower())
        if not user:
            # Perform a dummy hash comparison so a missing account takes the same
            # time as an existing one, preventing user-enumeration via timing.
            verify_password(password, _DUMMY_PASSWORD_HASH)
            raise UnauthorizedError("Invalid email or password")
        if not verify_password(password, user.hashed_password):
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

        # Atomically consume the refresh token. If a concurrent request already
        # rotated it, this returns False and we reject rather than minting a
        # second token pair from the same (single-use) refresh token.
        if not self.tokens.revoke_if_active(stored.id):
            raise UnauthorizedError("Refresh token revoked")
        return self._issue_tokens(user)

    def change_password(
        self,
        user_id: UUID,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        user = self.users.get_by_id(user_id)
        if not user or not verify_password(current_password, user.hashed_password):
            raise UnauthorizedError("Invalid current password")
        user.hashed_password = hash_password(new_password)
        # Invalidate every previously-issued token: refresh tokens are revoked
        # here, and stamping password_changed_at causes get_current_user to
        # reject any access token issued before this instant.
        user.password_changed_at = datetime.now(UTC)
        self.tokens.revoke_all_for_user(user_id)
        self.audit.record(
            AuditActions.USER_PASSWORD_CHANGED,
            "user",
            actor_user_id=user_id,
            entity_id=str(user_id),
            commit=True,
        )

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
        student_number: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        cohort: str | None = None,
        program: str | None = None,
        vendor_name: str | None = None,
        vendor_type: VendorType | None = None,
        department: str | None = None,
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

        if role == UserRole.student:
            StudentService(self.db).create_student(
                email=normalized_email,
                password=password,
                student_number=student_number,
                first_name=first_name,
                last_name=last_name,
                cohort=cohort,
                program=program,
                phone=phone,
                skip_user_creation=True,
                existing_user=user,
            )
        elif role == UserRole.vendor:
            UserAdminService(self.db).provision_vendor(
                user,
                name=vendor_name,
                vendor_type=vendor_type,
            )
        elif role == UserRole.staff:
            UserAdminService(self.db).provision_staff(
                user,
                first_name=first_name,
                last_name=last_name,
                department=department,
            )

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
