"""Production feature tests — auth, RBAC, QR, reports, audit."""

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.audit_log import AuditLog
from app.models.enums import UserRole, UserStatus, WalletStatus
from app.models.qr_session import QRSession
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.earning_rule import EarningRuleRepository
from app.services.auth_service import AuthService
from app.services.earning_service import EarningService
from app.services.redemption_service import RedemptionService


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


def test_auth_login(client: TestClient, staff_user, db_session):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": staff_user.email, "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    logs = AuditLogRepository(db_session).list_recent(10)
    assert any(log.action == "user.login" for log in logs)


def test_auth_login_pending_user(client: TestClient, db_session):
    user = User(
        email=f"pending-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.student,
        status=UserStatus.pending,
    )
    db_session.add(user)
    db_session.flush()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["code"] == "account_pending_approval"
    assert "pending admin approval" in data["detail"].lower()


def test_student_cannot_view_other_wallet(
    client: TestClient, student_with_wallet, db_session, system_accounts
):
    from app.services.student_service import StudentService

    other_student = StudentService(db_session).create_student(
        email=f"other-{uuid4()}@ptc.edu",
        password="password123",
        student_number=f"PTC-{uuid4().hex[:8]}",
        first_name="Other",
        last_name="Student",
    )
    from app.repositories.wallet import WalletRepository

    other_wallet = WalletRepository(db_session).get_by_student_id(other_student.id)
    assert other_wallet is not None
    token = create_access_token(str(student_with_wallet.user_id), role="student")
    response = client.get(
        f"/api/v1/wallets/{other_wallet.id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_staff_can_issue_reward(
    client: TestClient,
    student_with_wallet,
    staff_user,
    earning_rule,
    db_session,
    system_accounts,
):
    response = client.post(
        "/api/v1/staff/issue-reward",
        headers=_auth_header(staff_user),
        json={
            "student_id": str(student_with_wallet.id),
            "earning_rule_id": str(earning_rule.id),
            "notes": "Great work",
            "idempotency_key": f"staff-issue-{uuid4()}",
        },
    )
    assert response.status_code == 200
    assert Decimal(response.json()["new_balance"]) >= Decimal("5")


def test_vendor_can_redeem(
    client: TestClient,
    student_with_wallet,
    staff_user,
    earning_rule,
    vendor_with_account,
    reward_item,
    db_session,
    system_accounts,
):
    EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=f"fund-{uuid4()}",
        issued_by=staff_user.id,
    )
    plain, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    response = client.post(
        "/api/v1/vendor/redeem",
        headers=_auth_header(vendor_with_account.user),
        json={
            "qr_session_token": plain,
            "reward_item_id": str(reward_item.id),
            "idempotency_key": f"vendor-redeem-{uuid4()}",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["item_name"] == "Test Sandwich"
    assert "balance_after" in body


def test_vendor_cannot_redeem_expired_qr(
    db_session, student_with_wallet, vendor_with_account, reward_item, system_accounts
):
    token = "expired-token-xyz"
    session = QRSession(
        student_id=student_with_wallet.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) - timedelta(seconds=30),
    )
    db_session.add(session)
    db_session.commit()
    with pytest.raises(Exception):
        RedemptionService(db_session).redeem(
            vendor_user_id=vendor_with_account.user_id,
            qr_session_token=token,
            reward_item_id=reward_item.id,
            idempotency_key=f"exp-{uuid4()}",
        )


def test_vendor_cannot_redeem_used_qr_twice(
    db_session,
    student_with_wallet,
    staff_user,
    earning_rule,
    vendor_with_account,
    reward_item,
    system_accounts,
):
    EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=f"fund2-{uuid4()}",
        issued_by=staff_user.id,
    )
    plain, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    svc = RedemptionService(db_session)
    svc.redeem(
        vendor_user_id=vendor_with_account.user_id,
        qr_session_token=plain,
        reward_item_id=reward_item.id,
        idempotency_key=f"used-{uuid4()}",
    )
    from app.core.exceptions import AppError

    with pytest.raises(AppError) as exc_info:
        svc.redeem(
            vendor_user_id=vendor_with_account.user_id,
            qr_session_token=plain,
            reward_item_id=reward_item.id,
            idempotency_key=f"used2-{uuid4()}",
        )
    assert exc_info.value.code in ("session_used", "invalid_session")


def test_admin_can_view_reports(client: TestClient, admin_user, db_session, system_accounts):
    response = client.get(
        "/api/v1/admin/reports/overview",
        headers=_auth_header(admin_user),
    )
    assert response.status_code == 200
    assert "total_students" in response.json()


def test_weekly_bonus_idempotency(db_session, student_with_wallet, system_accounts):
    rules = EarningRuleRepository(db_session)
    att = rules.get_by_code("ATTENDANCE_ON_TIME")
    bonus = rules.get_by_code("PERFECT_ATTENDANCE_WEEK")
    if not att:
        from app.models.earning_rule import EarningRule

        att = EarningRule(code="ATTENDANCE_ON_TIME", name="On-time", token_amount=Decimal("1"), active=True)
        db_session.add(att)
    if not bonus:
        from app.models.earning_rule import EarningRule

        bonus = EarningRule(
            code="PERFECT_ATTENDANCE_WEEK", name="Perfect week", token_amount=Decimal("10"), active=True
        )
        db_session.add(bonus)
    db_session.flush()

    staff = User(
        email=f"staff2-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.staff,
        status=UserStatus.active,
    )
    db_session.add(staff)
    db_session.flush()

    today = datetime.now(UTC)
    for i in range(5):
        EarningService(db_session).issue_reward(
            student_id=student_with_wallet.id,
            earning_rule_id=att.id,
            notes=f"day {i}",
            idempotency_key=f"att-{student_with_wallet.id}-{i}-{uuid4()}",
            issued_by=staff.id,
        )

    iso_year, iso_week, _ = today.date().isocalendar()
    key = f"perfect-attendance-{student_with_wallet.id}-{iso_year}-W{iso_week:02d}"
    EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=bonus.id,
        notes="bonus",
        idempotency_key=key,
        issued_by=staff.id,
    )
    EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=bonus.id,
        notes="bonus dup",
        idempotency_key=key,
        issued_by=staff.id,
    )
    from app.services.wallet_service import WalletService

    balance = WalletService(db_session).get_balance(student_with_wallet.wallet.id)
    assert balance == Decimal("5") + Decimal("10")


def test_redeem_cannot_replay_foreign_idempotency_key(
    db_session,
    student_with_wallet,
    staff_user,
    earning_rule,
    vendor_with_account,
    reward_item,
    system_accounts,
):
    """A key harvested from another operation must never let a redemption
    'complete' without debiting the student (idempotency-replay hardening)."""
    from app.services.wallet_service import WalletService

    # Fund the wallet; capture the raw key a student could read from history.
    shared_key = f"shared-{uuid4()}"
    EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=shared_key,
        issued_by=staff_user.id,
    )
    balance_before = WalletService(db_session).get_balance(student_with_wallet.wallet.id)

    plain, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    receipt = RedemptionService(db_session).redeem(
        vendor_user_id=vendor_with_account.user_id,
        qr_session_token=plain,
        reward_item_id=reward_item.id,
        idempotency_key=shared_key,  # same key as the earn above
    )

    # The redemption really posts a debit rather than echoing the earn tx.
    balance_after = WalletService(db_session).get_balance(student_with_wallet.wallet.id)
    assert balance_after == balance_before - Decimal(reward_item.price_tokens)
    assert receipt["balance_after"] == balance_after


def test_two_vendors_reusing_same_weak_key_are_isolated(
    db_session,
    student_with_wallet,
    staff_user,
    earning_rule,
    vendor_with_account,
    reward_item,
    system_accounts,
):
    """Two vendors picking the same weak key must not share a receipt."""
    from app.models.enums import VendorStatus, VendorType
    from app.models.vendor import Vendor
    from app.services.system_accounts_service import SystemAccountsService

    # Fund generously so balance is not the limiting factor.
    for _ in range(3):
        EarningService(db_session).issue_reward(
            student_id=student_with_wallet.id,
            earning_rule_id=earning_rule.id,
            notes=None,
            idempotency_key=f"fund-{uuid4()}",
            issued_by=staff_user.id,
        )

    # A global (vendor-agnostic) item both vendors are allowed to redeem.
    from app.models.enums import RewardCategory
    from app.models.reward_item import RewardItem

    global_item = RewardItem(
        name="Campus Snack",
        category=RewardCategory.food_truck,
        price_tokens=Decimal("2.00"),
        vendor_id=None,
        active=True,
    )
    db_session.add(global_item)
    db_session.flush()

    weak_key = "12345678"
    plain1, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    receipt1 = RedemptionService(db_session).redeem(
        vendor_user_id=vendor_with_account.user_id,
        qr_session_token=plain1,
        reward_item_id=global_item.id,
        idempotency_key=weak_key,
    )

    # A second, unrelated vendor.
    other_user = User(
        email=f"vendor2-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.vendor,
        status=UserStatus.active,
    )
    db_session.add(other_user)
    db_session.flush()
    other_vendor = Vendor(
        user_id=other_user.id,
        name="Second Stand",
        vendor_type=VendorType.food_truck,
        status=VendorStatus.active,
    )
    db_session.add(other_vendor)
    db_session.flush()
    SystemAccountsService(db_session).ensure_vendor_account(other_vendor.id, other_vendor.name)

    plain2, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    receipt2 = RedemptionService(db_session).redeem(
        vendor_user_id=other_user.id,
        qr_session_token=plain2,
        reward_item_id=global_item.id,
        idempotency_key=weak_key,  # same weak key, different vendor
    )

    # Distinct redemptions — vendor 2 did not receive vendor 1's receipt.
    assert receipt1["redemption_id"] != receipt2["redemption_id"]
    assert receipt2["vendor_name"] == "Second Stand"


def test_wallet_totals_reflect_all_transactions(
    client: TestClient,
    student_with_wallet,
    staff_user,
    earning_rule,
    vendor_with_account,
    reward_item,
    db_session,
    system_accounts,
):
    """Lifetime totals come from the ledger aggregate, not a single 50-row page."""
    # earning_rule awards 5 each; issue 3 times = 15 earned.
    for _ in range(3):
        EarningService(db_session).issue_reward(
            student_id=student_with_wallet.id,
            earning_rule_id=earning_rule.id,
            notes=None,
            idempotency_key=f"fund-{uuid4()}",
            issued_by=staff_user.id,
        )
    # Redeem a 3-credit item once.
    plain, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    RedemptionService(db_session).redeem(
        vendor_user_id=vendor_with_account.user_id,
        qr_session_token=plain,
        reward_item_id=reward_item.id,
        idempotency_key=f"redeem-{uuid4()}",
    )

    token = create_access_token(str(student_with_wallet.user_id), role="student")
    response = client.get(
        f"/api/v1/wallets/{student_with_wallet.wallet.id}/totals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["total_earned"]) == Decimal("15.00")
    assert Decimal(body["total_redeemed"]) == Decimal("3.00")
    assert Decimal(body["balance"]) == Decimal("12.00")


def test_admin_redemptions_endpoint_returns_names(
    client: TestClient,
    admin_user,
    student_with_wallet,
    staff_user,
    earning_rule,
    vendor_with_account,
    reward_item,
    db_session,
    system_accounts,
):
    """Admin redemptions list shows real student/vendor/item names, not UUIDs."""
    EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=f"fund-{uuid4()}",
        issued_by=staff_user.id,
    )
    plain, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    RedemptionService(db_session).redeem(
        vendor_user_id=vendor_with_account.user_id,
        qr_session_token=plain,
        reward_item_id=reward_item.id,
        idempotency_key=f"redeem-{uuid4()}",
    )

    response = client.get("/api/v1/admin/redemptions", headers=_auth_header(admin_user))
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    row = rows[0]
    assert row["item_name"] == "Test Sandwich"
    assert row["vendor_name"] == "Campus Food Truck"
    assert row["student_name"] == student_with_wallet.full_name
    assert row["status"] == "completed"


def test_weekly_bonus_pays_out_for_prior_week(db_session, student_with_wallet, system_accounts):
    """The job scores the previous completed week, so a student with 5 attendance
    days last week receives the bonus (regression: it used to score the current
    week and never reach the threshold)."""
    from app.models.earning_event import EarningEvent
    from app.models.earning_rule import EarningRule
    from app.models.enums import EarningEventStatus
    from app.repositories.earning_rule import EarningRuleRepository
    from app.services.wallet_service import WalletService
    from app.workers.tasks import run_weekly_perfect_attendance_bonus

    rules = EarningRuleRepository(db_session)
    att = rules.get_by_code("ATTENDANCE_ON_TIME") or EarningRule(
        code="ATTENDANCE_ON_TIME", name="On-time", token_amount=Decimal("1"), active=True
    )
    bonus = rules.get_by_code("PERFECT_ATTENDANCE_WEEK") or EarningRule(
        code="PERFECT_ATTENDANCE_WEEK", name="Perfect week", token_amount=Decimal("10"), active=True
    )
    db_session.add_all([att, bonus])
    db_session.flush()

    staff = User(
        email=f"staff-wb-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.staff,
        status=UserStatus.active,
    )
    db_session.add(staff)
    db_session.flush()

    # Seed 5 distinct attendance days in the PREVIOUS week.
    today = datetime.now(UTC).date()
    prior_monday = today - timedelta(days=today.weekday() + 7)
    for i in range(5):
        day_dt = datetime.combine(
            prior_monday + timedelta(days=i), datetime.min.time()
        ).replace(hour=12, tzinfo=UTC)
        db_session.add(
            EarningEvent(
                student_id=student_with_wallet.id,
                rule_id=att.id,
                amount=Decimal("1"),
                status=EarningEventStatus.posted,
                issued_by=staff.id,
                idempotency_key=f"seed-att-{uuid4()}",
                created_at=day_dt,
            )
        )
    db_session.flush()

    balance_before = WalletService(db_session).get_balance(student_with_wallet.wallet.id)
    result = run_weekly_perfect_attendance_bonus(db_session)

    assert result["issued"] == 1
    balance_after = WalletService(db_session).get_balance(student_with_wallet.wallet.id)
    assert balance_after == balance_before + Decimal("10")


def test_audit_log_on_redemption(
    db_session,
    student_with_wallet,
    staff_user,
    earning_rule,
    vendor_with_account,
    reward_item,
    system_accounts,
):
    EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=f"audit-fund-{uuid4()}",
        issued_by=staff_user.id,
    )
    plain, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    RedemptionService(db_session).redeem(
        vendor_user_id=vendor_with_account.user_id,
        qr_session_token=plain,
        reward_item_id=reward_item.id,
        idempotency_key=f"audit-redeem-{uuid4()}",
    )
    logs = db_session.query(AuditLog).filter(AuditLog.action == "redemption.completed").all()
    assert len(logs) >= 1
