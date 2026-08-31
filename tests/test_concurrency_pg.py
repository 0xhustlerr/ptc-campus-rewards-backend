"""Real-concurrency tests against PostgreSQL.

The default suite runs on SQLite, which serializes access and therefore cannot
reproduce the row-locking and unique-violation races these tests target. These
tests spin up threads against a local Postgres so the idempotency/locking
behavior is exercised for real. They are skipped automatically when Postgres is
not reachable, so they never break a SQLite-only environment.

Run explicitly with:  pytest tests/test_concurrency_pg.py
"""

from __future__ import annotations

import hashlib
import os
import threading
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import AppError
from app.models import Base
from app.models.earning_event import EarningEvent
from app.models.enums import (
    RedemptionStatus,
    RewardCategory,
    UserRole,
    UserStatus,
    VendorStatus,
    VendorType,
)
from app.models.earning_rule import EarningRule
from app.models.qr_session import QRSession
from app.models.redemption import Redemption
from app.models.reward_item import RewardItem
from app.models.user import User
from app.models.vendor import Vendor
from app.core.security import hash_password
from app.services.earning_service import EarningService
from app.services.redemption_service import RedemptionService
from app.services.student_service import StudentService
from app.services.system_accounts_service import SystemAccountsService
from app.services.wallet_service import WalletService

PG_URL = os.environ.get(
    "TEST_PG_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/ptc_concurrency_test",
)


def _pg_available() -> bool:
    try:
        eng = create_engine(PG_URL)
        with eng.connect():
            pass
        eng.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_available(), reason="PostgreSQL not reachable for concurrency tests"
)


@pytest.fixture(scope="module")
def pg_sessionmaker():
    engine = create_engine(PG_URL, pool_size=10, max_overflow=10)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield Session
    engine.dispose()


def _seed_student(Session, *, funded: Decimal = Decimal("0")) -> dict:
    """Create system accounts, a staff user, a funded student, a rule, a vendor
    and an item. Returns the ids the tests need. Committed before threads run."""
    s = Session()
    try:
        SystemAccountsService(s).ensure_system_accounts()

        staff = User(
            email=f"staff-{uuid4()}@ptc.edu",
            hashed_password=hash_password("password123"),
            role=UserRole.staff,
            status=UserStatus.active,
        )
        s.add(staff)
        s.flush()

        student = StudentService(s).create_student(
            email=f"student-{uuid4()}@ptc.edu",
            password="password123",
            student_number=f"PTC-{uuid4().hex[:8]}",
            first_name="Race",
            last_name="Condition",
        )

        rule = EarningRule(
            code=f"RULE_{uuid4().hex[:6]}",
            name="Concurrency rule",
            token_amount=Decimal("5.00"),
            active=True,
        )
        s.add(rule)

        vendor_user = User(
            email=f"vendor-{uuid4()}@ptc.edu",
            hashed_password=hash_password("password123"),
            role=UserRole.vendor,
            status=UserStatus.active,
        )
        s.add(vendor_user)
        s.flush()
        vendor = Vendor(
            user_id=vendor_user.id,
            name="Concurrency Truck",
            vendor_type=VendorType.food_truck,
            status=VendorStatus.active,
        )
        s.add(vendor)
        s.flush()
        SystemAccountsService(s).ensure_vendor_account(vendor.id, vendor.name)

        item = RewardItem(
            name="Race Sandwich",
            category=RewardCategory.food_truck,
            price_tokens=Decimal("3.00"),
            vendor_id=vendor.id,
            inventory_count=5,
            active=True,
        )
        s.add(item)
        s.commit()

        ids = {
            "staff_id": staff.id,
            "student_id": student.id,
            "wallet_id": student.wallet.id,
            "rule_id": rule.id,
            "vendor_user_id": vendor_user.id,
            "item_id": item.id,
        }
    finally:
        s.close()

    if funded > 0:
        # Fund the wallet with committed credits so redeems have balance.
        s = Session()
        try:
            EarningService(s).issue_reward(
                student_id=ids["student_id"],
                earning_rule_id=ids["rule_id"],
                notes=None,
                idempotency_key=f"seed-fund-{uuid4()}",
                issued_by=ids["staff_id"],
            )
        finally:
            s.close()
    return ids


def _run_threads(worker, count: int) -> list:
    barrier = threading.Barrier(count)
    results: list = [None] * count

    def run(i):
        barrier.wait()
        results[i] = worker(i)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_same_key_issue_reward_posts_once(pg_sessionmaker):
    ids = _seed_student(pg_sessionmaker)
    key = f"issue-race-{uuid4()}"
    N = 8

    def worker(_i):
        s = pg_sessionmaker()
        try:
            ev = EarningService(s).issue_reward(
                student_id=ids["student_id"],
                earning_rule_id=ids["rule_id"],
                notes=None,
                idempotency_key=key,
                issued_by=ids["staff_id"],
            )
            return ("ok", str(ev.id))
        except AppError as exc:
            return ("app_error", exc.code)
        except Exception as exc:  # noqa: BLE001 - surface unexpected failures
            return ("error", repr(exc))
        finally:
            s.close()

    results = _run_threads(worker, N)

    # No unhandled errors (previously a duplicate-key insert surfaced a 500).
    unhandled = [r for r in results if r[0] == "error"]
    assert not unhandled, f"unhandled errors: {unhandled}"
    # At least one succeeded.
    assert any(r[0] == "ok" for r in results)

    verify = pg_sessionmaker()
    try:
        scoped = f"issue:{ids['staff_id']}:{key}"
        count = verify.scalar(
            select(func.count()).select_from(EarningEvent).where(
                EarningEvent.idempotency_key == scoped
            )
        )
        assert count == 1, f"expected exactly one earning event, got {count}"
        balance = WalletService(verify).get_balance(ids["wallet_id"])
        assert balance == Decimal("5.00"), f"balance double-counted: {balance}"
    finally:
        verify.close()


def test_concurrent_same_key_redeem_debits_once(pg_sessionmaker):
    ids = _seed_student(pg_sessionmaker, funded=Decimal("5.00"))

    # One single-use QR session, shared by all threads.
    s = pg_sessionmaker()
    try:
        plain, _ = RedemptionService(s).create_qr_session(ids["student_id"])
    finally:
        s.close()

    key = f"redeem-race-{uuid4()}"
    N = 8

    def worker(_i):
        s = pg_sessionmaker()
        try:
            receipt = RedemptionService(s).redeem(
                vendor_user_id=ids["vendor_user_id"],
                qr_session_token=plain,
                reward_item_id=ids["item_id"],
                idempotency_key=key,
            )
            return ("ok", receipt["redemption_id"])
        except AppError as exc:
            return ("app_error", exc.code)
        except Exception as exc:  # noqa: BLE001
            return ("error", repr(exc))
        finally:
            s.close()

    results = _run_threads(worker, N)

    unhandled = [r for r in results if r[0] == "error"]
    assert not unhandled, f"unhandled errors: {unhandled}"

    verify = pg_sessionmaker()
    try:
        completed = verify.scalar(
            select(func.count()).select_from(Redemption).where(
                Redemption.status == RedemptionStatus.completed,
                Redemption.student_id == ids["student_id"],
            )
        )
        assert completed == 1, f"expected exactly one completed redemption, got {completed}"
        balance = WalletService(verify).get_balance(ids["wallet_id"])
        assert balance == Decimal("2.00"), f"wallet debited more than once: {balance}"
        item = verify.get(RewardItem, ids["item_id"])
        assert item.inventory_count == 4, f"inventory decremented wrong: {item.inventory_count}"
    finally:
        verify.close()


def test_concurrent_distinct_key_redeem_of_one_qr_succeeds_once(pg_sessionmaker):
    """Different keys but the same single-use QR: exactly one redeem may win."""
    ids = _seed_student(pg_sessionmaker, funded=Decimal("5.00"))
    s = pg_sessionmaker()
    try:
        plain, _ = RedemptionService(s).create_qr_session(ids["student_id"])
    finally:
        s.close()

    N = 6

    def worker(i):
        s = pg_sessionmaker()
        try:
            receipt = RedemptionService(s).redeem(
                vendor_user_id=ids["vendor_user_id"],
                qr_session_token=plain,
                reward_item_id=ids["item_id"],
                idempotency_key=f"distinct-{i}-{uuid4()}",
            )
            return ("ok", receipt["redemption_id"])
        except AppError as exc:
            return ("app_error", exc.code)
        except Exception as exc:  # noqa: BLE001
            return ("error", repr(exc))
        finally:
            s.close()

    results = _run_threads(worker, N)

    unhandled = [r for r in results if r[0] == "error"]
    assert not unhandled, f"unhandled errors: {unhandled}"
    ok = [r for r in results if r[0] == "ok"]
    assert len(ok) == 1, f"single-use QR allowed {len(ok)} redemptions"

    verify = pg_sessionmaker()
    try:
        balance = WalletService(verify).get_balance(ids["wallet_id"])
        assert balance == Decimal("2.00"), f"unexpected balance: {balance}"
    finally:
        verify.close()
