"""Self-service password change tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.services.audit_service import AuditActions


def _auth_header(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), role=user.role.value)}"}


def test_change_password_success(client: TestClient, db_session, student_with_wallet):
    user = student_with_wallet.user
    response = client.post(
        "/api/v1/auth/change-password",
        headers=_auth_header(user),
        json={
            "current_password": "password123",
            "new_password": "newSecure99!",
        },
    )
    assert response.status_code == 204
    db_session.refresh(user)
    assert verify_password("newSecure99!", user.hashed_password)
    assert not verify_password("password123", user.hashed_password)

    logs = AuditLogRepository(db_session).list_recent(10)
    assert any(log.action == AuditActions.USER_PASSWORD_CHANGED for log in logs)


def test_change_password_wrong_current(client: TestClient, student_with_wallet):
    user = student_with_wallet.user
    response = client.post(
        "/api/v1/auth/change-password",
        headers=_auth_header(user),
        json={
            "current_password": "wrongpassword",
            "new_password": "newSecure99!",
        },
    )
    assert response.status_code == 401


def test_change_password_same_as_current(client: TestClient, student_with_wallet):
    user = student_with_wallet.user
    response = client.post(
        "/api/v1/auth/change-password",
        headers=_auth_header(user),
        json={
            "current_password": "password123",
            "new_password": "password123",
        },
    )
    assert response.status_code == 422


def _backdated_access_token(user: User, *, seconds_ago: int) -> str:
    """Mint an access token with an `iat` in the past (real tokens predate a
    later password change; without this the test would collide within 1s)."""
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from jose import jwt

    from app.core.config import get_settings

    settings = get_settings()
    issued = datetime.now(UTC) - timedelta(seconds=seconds_ago)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": "access",
        "iat": issued,
        "exp": issued + timedelta(minutes=30),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def test_access_token_invalidated_after_password_change(client: TestClient, student_with_wallet):
    user = student_with_wallet.user
    token = _backdated_access_token(user, seconds_ago=60)
    header = {"Authorization": f"Bearer {token}"}

    # Token works before the change.
    assert client.get("/api/v1/auth/me", headers=header).status_code == 200

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=header,
        json={"current_password": "password123", "new_password": "newSecure99!"},
    )
    assert changed.status_code == 204

    # The same access token (issued before the change) is now rejected.
    assert client.get("/api/v1/auth/me", headers=header).status_code == 401


def test_change_password_admin(client: TestClient, db_session):
    admin = User(
        email=f"admin-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db_session.add(admin)
    db_session.flush()

    response = client.post(
        "/api/v1/auth/change-password",
        headers=_auth_header(admin),
        json={
            "current_password": "password123",
            "new_password": "adminNewPass1!",
        },
    )
    assert response.status_code == 204
    db_session.refresh(admin)
    assert verify_password("adminNewPass1!", admin.hashed_password)
