"""OAuth 2.0 style authentication — closed-loop campus access."""

from fastapi import APIRouter, Request

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterUserRequest,
    SelfRegisterRequest,
    TokenResponse,
    UserRead,
)
from app.services.auth_service import AuthService
from app.services.user_admin_service import UserAdminService
from app.utils.mappers import user_to_read

router = APIRouter()
settings = get_settings()


@router.post("/login", response_model=TokenResponse, summary="Login and receive PTC Credits API tokens")
@limiter.limit(settings.rate_limit_auth)
def login(request: Request, db: DbSession, body: LoginRequest) -> TokenResponse:
    return AuthService(db).login(body.email, body.password)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_auth)
def refresh_token(request: Request, db: DbSession, body: RefreshTokenRequest) -> TokenResponse:
    return AuthService(db).refresh(body.refresh_token)


@router.post("/logout", status_code=204)
@limiter.limit(settings.rate_limit_auth)
def logout(
    request: Request,
    db: DbSession,
    body: LogoutRequest,
    current_user: CurrentUser,
) -> None:
    AuthService(db).logout(body.refresh_token, current_user_id=current_user.id)


@router.post("/register", response_model=UserRead, status_code=201, summary="Self-register account (pending admin approval)")
def self_register_user(db: DbSession, body: SelfRegisterRequest) -> UserRead:
    user = AuthService(db).self_register(
        email=body.email,
        password=body.password,
        role=body.role,
        phone=body.phone,
        student_number=body.student_number,
        first_name=body.first_name,
        last_name=body.last_name,
        cohort=body.cohort,
        program=body.program,
        vendor_name=body.vendor_name,
        vendor_type=body.vendor_type,
    )
    return user_to_read(user)


@router.post("/register/admin", response_model=UserRead, status_code=201, summary="Admin creates a user")
def register_user(db: DbSession, body: RegisterUserRequest, admin: AdminUser) -> UserRead:
    user = UserAdminService(db).register_user(body, created_by=admin.id)
    return user_to_read(user)


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> UserRead:
    return user_to_read(current_user)
