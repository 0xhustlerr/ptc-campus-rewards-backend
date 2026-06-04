"""Admin account provisioning tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.services.audit_service import AuditActions


def _auth_header(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), role=user.role.value)}"}


def _create_user(db_session, *, role: UserRole) -> User:
    user = User(
        email=f"{role.value}-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=role,
        status=UserStatus.active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_create_admin_requires_authentication(client: TestClient):
    response = client.post(
        "/api/v1/admin/admins",
        json={"email": f"newadmin-{uuid4()}@ptc.edu", "password": "password123"},
    )
    assert response.status_code == 401


def test_create_admin_forbidden_for_staff(client: TestClient, db_session):
    staff = _create_user(db_session, role=UserRole.staff)
    response = client.post(
        "/api/v1/admin/admins",
        headers=_auth_header(staff),
        json={"email": f"newadmin-{uuid4()}@ptc.edu", "password": "password123"},
    )
    assert response.status_code == 403


def test_admin_can_create_admin_account(client: TestClient, db_session):
    admin = _create_user(db_session, role=UserRole.admin)
    new_email = f"newadmin-{uuid4()}@ptc.edu"

    response = client.post(
        "/api/v1/admin/admins",
        headers=_auth_header(admin),
        json={"email": new_email, "password": "password123", "phone": "+15550100"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == new_email
    assert body["role"] == "admin"
    assert body["status"] == "active"
    assert body["phone"] == "+15550100"
    assert "created_at" in body


def test_create_admin_duplicate_email_returns_conflict(client: TestClient, db_session):
    admin = _create_user(db_session, role=UserRole.admin)
    email = f"dupadmin-{uuid4()}@ptc.edu"

    first = client.post(
        "/api/v1/admin/admins",
        headers=_auth_header(admin),
        json={"email": email, "password": "password123"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/admin/admins",
        headers=_auth_header(admin),
        json={"email": email, "password": "password123"},
    )
    assert second.status_code == 409
    assert second.json()["code"] == "conflict"


def test_register_admin_via_generic_admin_endpoint_still_forbidden(client: TestClient, db_session):
    admin = _create_user(db_session, role=UserRole.admin)

    response = client.post(
        "/api/v1/auth/register/admin",
        headers=_auth_header(admin),
        json={
            "email": f"blockedadmin-{uuid4()}@ptc.edu",
            "password": "password123",
            "role": "admin",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "admin_provision_forbidden"


def test_create_admin_writes_audit_log(client: TestClient, db_session):
    admin = _create_user(db_session, role=UserRole.admin)
    new_email = f"auditedadmin-{uuid4()}@ptc.edu"

    response = client.post(
        "/api/v1/admin/admins",
        headers=_auth_header(admin),
        json={"email": new_email, "password": "password123"},
    )
    assert response.status_code == 201
    created_id = response.json()["id"]

    logs = AuditLogRepository(db_session).list_recent(20)
    matching = [
        log
        for log in logs
        if log.action == AuditActions.ADMIN_CREATED
        and log.entity_id == created_id
        and log.actor_user_id == admin.id
    ]
    assert len(matching) == 1


def test_list_admin_accounts(client: TestClient, db_session):
    admin = _create_user(db_session, role=UserRole.admin)
    _create_user(db_session, role=UserRole.admin)

    response = client.get(
        "/api/v1/admin/admins",
        headers=_auth_header(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 2
    assert all(item["role"] == "admin" for item in body)
