"""Student self-registration and approval workflow."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.student import StudentRepository
from app.repositories.wallet import WalletRepository


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


def test_self_register_student_requires_profile_fields(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"student-{uuid4()}@ptc.edu",
            "password": "password123",
            "role": "student",
        },
    )
    assert response.status_code == 422


def test_self_register_student_creates_profile_and_wallet(client: TestClient, db_session):
    email = f"student-{uuid4()}@ptc.edu"
    student_number = f"PTC-{uuid4().hex[:8]}"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "role": "student",
            "student_number": student_number,
            "first_name": "Jane",
            "last_name": "Doe",
            "cohort": "Fall 2026",
            "program": "Barbering",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["role"] == "student"

    user_id = UUID(data["id"])
    student = StudentRepository(db_session).get_by_user_id(user_id)
    assert student is not None
    assert student.student_number == student_number

    wallet = WalletRepository(db_session).get_by_student_id(student.id)
    assert wallet is not None


def test_approve_student_then_wallet_endpoints_work(
    client: TestClient, db_session, admin_user, system_accounts
):
    email = f"student-{uuid4()}@ptc.edu"
    password = "password123"
    student_number = f"PTC-{uuid4().hex[:8]}"

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "student",
            "student_number": student_number,
            "first_name": "Alex",
            "last_name": "Rivera",
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
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    students_me = client.get("/api/v1/students/me", headers=headers)
    assert students_me.status_code == 200
    assert students_me.json()["student_number"] == student_number

    wallets_me = client.get("/api/v1/wallets/me", headers=headers)
    assert wallets_me.status_code == 200
    assert wallets_me.json()["student_number"] == student_number


def test_pending_registrations_include_student_profile(
    client: TestClient, admin_user
):
    email = f"pending-list-{uuid4()}@ptc.edu"
    student_number = f"PTC-{uuid4().hex[:8]}"

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "role": "student",
            "student_number": student_number,
            "first_name": "Sam",
            "last_name": "Chen",
            "cohort": "Spring 2026",
            "program": "Cosmetology",
        },
    )
    assert register.status_code == 201
    user_id = register.json()["id"]

    response = client.get(
        "/api/v1/admin/users/pending",
        headers=_auth_header(admin_user),
    )
    assert response.status_code == 200
    pending = response.json()
    match = next((item for item in pending if item["id"] == user_id), None)
    assert match is not None
    assert match["email"] == email
    profile = match["student_profile"]
    assert profile is not None
    assert profile["student_number"] == student_number
    assert profile["first_name"] == "Sam"
    assert profile["last_name"] == "Chen"
    assert profile["cohort"] == "Spring 2026"
    assert profile["program"] == "Cosmetology"


def test_approve_legacy_student_without_profile_requires_fields(
    client: TestClient, db_session, admin_user
):
    user = User(
        email=f"legacy-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.student,
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
    assert response.json()["code"] == "student_profile_missing"


def test_approve_legacy_student_with_admin_profile(
    client: TestClient, db_session, admin_user, system_accounts
):
    email = f"legacy-{uuid4()}@ptc.edu"
    password = "password123"
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.student,
        status=UserStatus.pending,
    )
    db_session.add(user)
    db_session.flush()

    student_number = f"PTC-{uuid4().hex[:8]}"
    approve = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        headers=_auth_header(admin_user),
        json={
            "status": "active",
            "student_number": student_number,
            "first_name": "Legacy",
            "last_name": "Student",
        },
    )
    assert approve.status_code == 200

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/students/me", headers=headers).status_code == 200
    assert client.get("/api/v1/wallets/me", headers=headers).status_code == 200
