"""Admin earning rule catalog tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User


def _admin(db_session) -> User:
    user = User(
        email=f"admin-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _auth_header(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), role=user.role.value)}"}


def _payload(code: str) -> dict:
    return {"code": code, "name": "Practical skills evaluation", "token_amount": "1"}


def test_create_earning_rule(client: TestClient, db_session):
    admin = _admin(db_session)
    code = f"RULE_{uuid4().hex[:6]}"
    response = client.post(
        "/api/v1/admin/earning-rules", headers=_auth_header(admin), json=_payload(code)
    )
    assert response.status_code == 201
    assert response.json()["code"] == code


def test_duplicate_earning_rule_code_returns_conflict(client: TestClient, db_session):
    admin = _admin(db_session)
    code = f"RULE_{uuid4().hex[:6]}"
    headers = _auth_header(admin)

    first = client.post("/api/v1/admin/earning-rules", headers=headers, json=_payload(code))
    assert first.status_code == 201

    second = client.post("/api/v1/admin/earning-rules", headers=headers, json=_payload(code))
    assert second.status_code == 409
    body = second.json()
    assert body["code"] == "conflict"
    assert code in body["detail"]

    # The session survives the rejected insert.
    listing = client.get("/api/v1/admin/earning-rules", headers=headers)
    assert listing.status_code == 200


def test_earning_rule_rejects_non_positive_amount(client: TestClient, db_session):
    admin = _admin(db_session)
    headers = _auth_header(admin)
    payload = _payload(f"RULE_{uuid4().hex[:6]}")
    payload["token_amount"] = "0"
    response = client.post("/api/v1/admin/earning-rules", headers=headers, json=payload)
    assert response.status_code == 422


def test_reward_item_rejects_negative_inventory(client: TestClient, db_session):
    admin = _admin(db_session)
    headers = _auth_header(admin)
    response = client.post(
        "/api/v1/admin/reward-items",
        headers=headers,
        json={
            "name": "Cap",
            "category": "student_perks",
            "price_tokens": "0",
            "inventory_count": -1,
        },
    )
    assert response.status_code == 422


def test_health_detail_requires_admin(client: TestClient, db_session):
    # Unauthenticated: version + dependency status must not be exposed.
    unauth = client.get("/api/v1/health/detail")
    assert unauth.status_code == 401

    admin = _admin(db_session)
    ok = client.get("/api/v1/health/detail", headers=_auth_header(admin))
    assert ok.status_code == 200
    assert "version" in ok.json()
