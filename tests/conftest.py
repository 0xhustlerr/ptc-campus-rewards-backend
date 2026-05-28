"""Pytest fixtures with in-memory SQLite and ledger test helpers."""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "postgresql://ptc:ptc@localhost/ptc_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-minimum-32-characters-long")

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import Base
from app.models.enums import AccountType, UserRole, UserStatus, VendorStatus, VendorType
from app.models.earning_rule import EarningRule
from app.models.ledger_account import LedgerAccount
from app.models.reward_item import RewardItem
from app.models.user import User
from app.models.vendor import Vendor
from app.services.student_service import StudentService
from app.services.system_accounts_service import SystemAccountsService


@pytest.fixture(scope="session")
def engine():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def system_accounts(db_session):
    pool, adjustment = SystemAccountsService(db_session).ensure_system_accounts()
    db_session.flush()
    return {"pool": pool, "adjustment": adjustment}


@pytest.fixture
def staff_user(db_session) -> User:
    user = User(
        email=f"staff-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.staff,
        status=UserStatus.active,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def student_with_wallet(db_session, system_accounts):
    student = StudentService(db_session).create_student(
        email=f"student-{uuid4()}@ptc.edu",
        password="password123",
        student_number=f"PTC-{uuid4().hex[:8]}",
        first_name="Test",
        last_name="Student",
    )
    db_session.expire_all()
    student = StudentService(db_session).get_by_id(student.id)
    return student


@pytest.fixture
def earning_rule(db_session) -> EarningRule:
    rule = EarningRule(
        code=f"TEST_RULE_{uuid4().hex[:6]}",
        name="Test attendance",
        token_amount=Decimal("5.00"),
        active=True,
    )
    db_session.add(rule)
    db_session.flush()
    return rule


@pytest.fixture
def vendor_with_account(db_session, system_accounts) -> Vendor:
    user = User(
        email=f"vendor-{uuid4()}@ptc.edu",
        hashed_password=hash_password("password123"),
        role=UserRole.vendor,
        status=UserStatus.active,
    )
    db_session.add(user)
    db_session.flush()
    vendor = Vendor(
        user_id=user.id,
        name="Campus Food Truck",
        vendor_type=VendorType.food_truck,
        status=VendorStatus.active,
    )
    db_session.add(vendor)
    db_session.flush()
    SystemAccountsService(db_session).ensure_vendor_account(vendor.id, vendor.name)
    db_session.flush()
    return vendor


@pytest.fixture
def reward_item(db_session, vendor_with_account) -> RewardItem:
    from app.models.enums import RewardCategory

    item = RewardItem(
        name="Test Sandwich",
        category=RewardCategory.food_truck,
        price_tokens=Decimal("3.00"),
        vendor_id=vendor_with_account.id,
        active=True,
    )
    db_session.add(item)
    db_session.flush()
    return item
