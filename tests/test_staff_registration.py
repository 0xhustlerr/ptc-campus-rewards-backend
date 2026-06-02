"""Staff self-registration and approval workflow."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.staff import StaffRepository


def _auth_header(user: User) -> dict:
    token = create_access_token(str(user.id), role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(db_session) -> User:
    user = User(
        email=f"admin-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_self_register_staff_requires_profile_fields(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"staff-{uuid4()}@ptc.edu",
            "password": "password123",
            "role": "staff",
        },
    )
    assert response.status_code == 422


def test_self_register_staff_creates_profile(client: TestClient, db_session):
    email = f"staff-{uuid4()}@ptc.edu"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "role": "staff",
            "first_name": "Jordan",
            "last_name": "Lee",
            "department": "Admissions",
        },
    )
    assert response.status_code == 201
    user_id = UUID(response.json()["id"])

    staff = StaffRepository(db_session).get_by_user_id(user_id)
    assert staff is not None
    assert staff.first_name == "Jordan"
    assert staff.last_name == "Lee"
    assert staff.department == "Admissions"


def test_pending_registrations_include_staff_profile(client: TestClient, admin_user):
    email = f"pending-staff-{uuid4()}@ptc.edu"

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "role": "staff",
            "first_name": "Sam",
            "last_name": "Rivera",
            "department": "Student Services",
        },
    )
    assert register.status_code == 201
    user_id = register.json()["id"]

    response = client.get(
        "/api/v1/admin/users/pending",
        headers=_auth_header(admin_user),
    )
    assert response.status_code == 200
    match = next((item for item in response.json() if item["id"] == user_id), None)
    assert match is not None
    profile = match["staff_profile"]
    assert profile is not None
    assert profile["first_name"] == "Sam"
    assert profile["last_name"] == "Rivera"
    assert profile["department"] == "Student Services"


def test_approve_staff_then_staff_students_endpoint_works(
    client: TestClient, admin_user, system_accounts
):
    email = f"staff-approve-{uuid4()}@ptc.edu"
    password = "password123"

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "staff",
            "first_name": "Alex",
            "last_name": "Kim",
        },
    )
    assert register.status_code == 201
    user_id = register.json()["id"]

    approve = client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        headers=_auth_header(admin_user),
        json={"status": "active"},
    )
    assert approve.status_code == 200

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    students = client.get("/api/v1/staff/students", headers=headers)
    assert students.status_code == 200

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    profile = me.json()["staff_profile"]
    assert profile is not None
    assert profile["first_name"] == "Alex"
    assert profile["last_name"] == "Kim"


def test_approve_legacy_staff_without_profile_requires_fields(
    client: TestClient, db_session, admin_user
):
    user = User(
        email=f"legacy-staff-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.staff,
        status=UserStatus.pending,
    )
    db_session.add(user)
    db_session.flush()

    response = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        headers=_auth_header(admin_user),
        json={"status": "active"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "staff_profile_missing"


def test_approve_legacy_staff_with_admin_profile(client: TestClient, db_session, admin_user):
    email = f"legacy-staff-backfill-{uuid4()}@ptc.edu"
    password = "password123"
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.staff,
        status=UserStatus.pending,
    )
    db_session.add(user)
    db_session.flush()

    approve = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        headers=_auth_header(admin_user),
        json={
            "status": "active",
            "first_name": "Legacy",
            "last_name": "Staff",
            "department": "Registrar",
        },
    )
    assert approve.status_code == 200

    staff = StaffRepository(db_session).get_by_user_id(user.id)
    assert staff is not None
    assert staff.department == "Registrar"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/staff/students", headers=headers).status_code == 200
