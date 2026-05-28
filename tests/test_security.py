"""Security and auth hardening tests."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.enums import UserRole, UserStatus
from app.models.oauth import OAuthRefreshToken
from app.models.user import User
from app.services.auth_service import AuthService


def _auth_header(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), role=user.role.value)}"}


def test_logout_cannot_revoke_other_users_token(db_session, client: TestClient):
    user_a = User(
        email=f"a-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.student,
        status=UserStatus.active,
    )
    user_b = User(
        email=f"b-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.student,
        status=UserStatus.active,
    )
    db_session.add_all([user_a, user_b])
    db_session.flush()

    refresh_b, expires = create_refresh_token(str(user_b.id))
    import hashlib

    db_session.add(
        OAuthRefreshToken(
            user_id=user_b.id,
            token_hash=hashlib.sha256(refresh_b.encode()).hexdigest(),
            expires_at=expires,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/logout",
        headers=_auth_header(user_a),
        json={"refresh_token": refresh_b},
    )
    assert response.status_code == 403


def test_invalid_jwt_sub_returns_401(client: TestClient):
    token = create_access_token("not-a-valid-uuid", role="student")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_register_admin_role_forbidden(client: TestClient, db_session):
    admin = User(
        email=f"admin-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db_session.add(admin)
    db_session.flush()

    response = client.post(
        "/api/v1/auth/register",
        headers=_auth_header(admin),
        json={
            "email": f"newadmin-{uuid4()}@ptc.edu",
            "password": "password123",
            "role": "admin",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "admin_provision_forbidden"


def test_refresh_token_user_binding(db_session):
    import hashlib

    from app.core.exceptions import UnauthorizedError

    user_a = User(
        email=f"refresh-a-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.staff,
        status=UserStatus.active,
    )
    user_b = User(
        email=f"refresh-b-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.staff,
        status=UserStatus.active,
    )
    db_session.add_all([user_a, user_b])
    db_session.flush()

    refresh, expires = create_refresh_token(str(user_a.id))
    db_session.add(
        OAuthRefreshToken(
            user_id=user_b.id,
            token_hash=hashlib.sha256(refresh.encode()).hexdigest(),
            expires_at=expires,
        )
    )
    db_session.commit()

    with pytest.raises(UnauthorizedError):
        AuthService(db_session).refresh(refresh)

    tokens = AuthService(db_session).login(user_a.email, "password123")
    assert AuthService(db_session).refresh(tokens.refresh_token).access_token
