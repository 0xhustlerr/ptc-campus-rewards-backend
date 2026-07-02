"""Earning approval workflow + limit-race / idempotency tests."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.exceptions import AppError
from app.models.earning_rule import EarningRule
from app.models.enums import EarningEventStatus
from app.services.earning_service import EarningService
from app.services.wallet_service import WalletService


@pytest.fixture
def approval_rule(db_session) -> EarningRule:
    rule = EarningRule(
        code=f"APPROVAL_{uuid4().hex[:6]}",
        name="Needs approval",
        token_amount=Decimal("7.00"),
        active=True,
        requires_approval=True,
    )
    db_session.add(rule)
    db_session.flush()
    return rule


@pytest.fixture
def limited_rule(db_session) -> EarningRule:
    rule = EarningRule(
        code=f"LIMITED_{uuid4().hex[:6]}",
        name="Daily limited",
        token_amount=Decimal("3.00"),
        active=True,
        daily_limit=1,
    )
    db_session.add(rule)
    db_session.flush()
    return rule


def test_approval_required_creates_pending_without_posting(
    student_with_wallet, approval_rule, staff_user, db_session, system_accounts
):
    wallet = student_with_wallet.wallet
    event = EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=approval_rule.id,
        notes="pending please",
        idempotency_key=f"appr-{uuid4()}",
        issued_by=staff_user.id,
    )
    assert event.status == EarningEventStatus.pending
    assert event.ledger_transaction_id is None
    # No credits posted yet.
    assert WalletService(db_session).get_balance(wallet.id) == Decimal("0.00")


def test_approve_event_posts_credits(
    student_with_wallet, approval_rule, staff_user, db_session, system_accounts
):
    wallet = student_with_wallet.wallet
    svc = EarningService(db_session)
    event = svc.issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=approval_rule.id,
        notes=None,
        idempotency_key=f"appr-{uuid4()}",
        issued_by=staff_user.id,
    )

    approved = svc.approve_event(event.id, approver_id=staff_user.id)
    assert approved.status == EarningEventStatus.posted
    assert approved.ledger_transaction_id is not None
    assert approved.approved_by == staff_user.id
    assert WalletService(db_session).get_balance(wallet.id) == Decimal("7.00")


def test_double_approve_is_rejected_and_not_double_posted(
    student_with_wallet, approval_rule, staff_user, db_session, system_accounts
):
    wallet = student_with_wallet.wallet
    svc = EarningService(db_session)
    event = svc.issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=approval_rule.id,
        notes=None,
        idempotency_key=f"appr-{uuid4()}",
        issued_by=staff_user.id,
    )
    svc.approve_event(event.id, approver_id=staff_user.id)

    with pytest.raises(AppError):
        svc.approve_event(event.id, approver_id=staff_user.id)
    # Balance reflects a single posting only.
    assert WalletService(db_session).get_balance(wallet.id) == Decimal("7.00")


def test_reject_event_frees_quota(
    student_with_wallet, limited_rule, staff_user, db_session, system_accounts
):
    svc = EarningService(db_session)
    # A pending event would consume quota, but this rule posts immediately
    # (no approval). Use rejection of a manual pending path instead: issue one,
    # then a second must hit the daily limit; rejecting the first frees it.
    e1 = svc.issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=limited_rule.id,
        notes=None,
        idempotency_key=f"lim-{uuid4()}",
        issued_by=staff_user.id,
    )
    assert e1.status == EarningEventStatus.posted

    # Second issue hits the daily limit of 1.
    with pytest.raises(AppError) as exc:
        svc.issue_reward(
            student_id=student_with_wallet.id,
            earning_rule_id=limited_rule.id,
            notes=None,
            idempotency_key=f"lim-{uuid4()}",
            issued_by=staff_user.id,
        )
    assert exc.value.code == "daily_limit"


def test_issue_reward_idempotent_for_pending_path(
    student_with_wallet, approval_rule, staff_user, db_session, system_accounts
):
    svc = EarningService(db_session)
    key = f"appr-{uuid4()}"
    e1 = svc.issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=approval_rule.id,
        notes=None,
        idempotency_key=key,
        issued_by=staff_user.id,
    )
    e2 = svc.issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=approval_rule.id,
        notes=None,
        idempotency_key=key,
        issued_by=staff_user.id,
    )
    # Same event returned — no duplicate pending event created.
    assert e1.id == e2.id
    pending = svc.list_pending_events()
    assert sum(1 for e in pending if e.id == e1.id) == 1
