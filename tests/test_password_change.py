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
