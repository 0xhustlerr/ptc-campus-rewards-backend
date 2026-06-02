"""Vendor self-registration and approval workflow."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.vendor import VendorRepository


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


def test_self_register_vendor_requires_profile_fields(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"vendor-{uuid4()}@ptc.edu",
            "password": "password123",
            "role": "vendor",
        },
    )
    assert response.status_code == 422


def test_self_register_vendor_creates_profile(client: TestClient, db_session, system_accounts):
    email = f"vendor-{uuid4()}@ptc.edu"
    vendor_name = "Campus Snacks"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "role": "vendor",
            "vendor_name": vendor_name,
            "vendor_type": "food_truck",
        },
    )
    assert response.status_code == 201
    user_id = UUID(response.json()["id"])

    vendor = VendorRepository(db_session).get_by_user_id(user_id)
    assert vendor is not None
    assert vendor.name == vendor_name
    assert vendor.vendor_type.value == "food_truck"


def test_pending_registrations_include_vendor_profile(client: TestClient, admin_user, system_accounts):
    email = f"pending-vendor-{uuid4()}@ptc.edu"
    vendor_name = "PTC Perks Booth"

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "role": "vendor",
            "vendor_name": vendor_name,
            "vendor_type": "campus_perk",
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
    profile = match["vendor_profile"]
    assert profile is not None
    assert profile["name"] == vendor_name
    assert profile["vendor_type"] == "campus_perk"


def test_approve_vendor_then_redemptions_endpoint_works(
    client: TestClient, admin_user, system_accounts
):
    email = f"vendor-approve-{uuid4()}@ptc.edu"
    password = "password123"

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "vendor",
            "vendor_name": "Approved Truck",
            "vendor_type": "food_truck",
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

    redemptions = client.get("/api/v1/vendor/redemptions", headers=headers)
    assert redemptions.status_code == 200
    assert redemptions.json() == []


def test_approve_legacy_vendor_without_profile_requires_fields(
    client: TestClient, db_session, admin_user
):
    user = User(
        email=f"legacy-vendor-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.vendor,
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
    assert response.json()["code"] == "vendor_profile_missing"


def test_approve_legacy_vendor_with_admin_profile(
    client: TestClient, db_session, admin_user, system_accounts
):
    email = f"legacy-vendor-backfill-{uuid4()}@ptc.edu"
    password = "password123"
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.vendor,
        status=UserStatus.pending,
    )
    db_session.add(user)
    db_session.flush()

    approve = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        headers=_auth_header(admin_user),
        json={
            "status": "active",
            "vendor_name": "Backfill Store",
            "vendor_type": "school_store",
        },
    )
    assert approve.status_code == 200

    vendor = VendorRepository(db_session).get_by_user_id(user.id)
    assert vendor is not None
    assert vendor.name == "Backfill Store"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/vendor/redemptions", headers=headers).status_code == 200
