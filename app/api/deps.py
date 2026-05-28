"""FastAPI dependencies: DB session, current user, role guards."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.auth_utils import parse_user_id
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import safe_decode_token
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.student import StudentRepository
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    payload = safe_decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired access token")

    user = UserRepository(db).get_by_id(parse_user_id(payload.get("sub")))
    if not user or user.status != UserStatus.active:
        raise UnauthorizedError("User not found or inactive")
    return user


def require_role(role: UserRole) -> Callable:
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role != role:
            raise ForbiddenError(f"Requires role: {role.value}")
        return user

    return checker


def require_any_role(*roles: UserRole) -> Callable:
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise ForbiddenError(f"Requires one of: {', '.join(r.value for r in roles)}")
        return user

    return checker


require_roles = require_any_role


def require_own_wallet(wallet_id: uuid.UUID, user: User, db: Session) -> None:
    """Students may only access their own wallet; staff/admin may access any."""
    if user.role in (UserRole.staff, UserRole.admin):
        return
    if user.role != UserRole.student:
        raise ForbiddenError()
    student = StudentRepository(db).get_by_user_id(user.id)
    if not student or not student.wallet or student.wallet.id != wallet_id:
        raise ForbiddenError("Cannot access this wallet")


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]

StudentUser = Annotated[User, Depends(require_role(UserRole.student))]
StaffUser = Annotated[User, Depends(require_any_role(UserRole.staff, UserRole.admin))]
VendorUser = Annotated[User, Depends(require_any_role(UserRole.vendor, UserRole.admin))]
AdminUser = Annotated[User, Depends(require_role(UserRole.admin))]
