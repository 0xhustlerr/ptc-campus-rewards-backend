"""Ledger double-entry tests for PTC Credits."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.exceptions import InsufficientCreditsError, LedgerError
from app.models.enums import EntryDirection, TransactionStatus, TransactionType
from app.services.earning_service import EarningService
from app.services.ledger_service import LedgerService
from app.services.redemption_service import RedemptionService
from app.services.wallet_service import WalletService


def test_wallet_creation(student_with_wallet, db_session):
    assert student_with_wallet.wallet is not None
    assert student_with_wallet.wallet.currency_code == "PTC"
    accounts = student_with_wallet.wallet.ledger_accounts
    assert any(a.account_type.value == "student_wallet" for a in accounts)


def test_earn_transaction(student_with_wallet, earning_rule, staff_user, db_session, system_accounts):
    wallet = student_with_wallet.wallet
    event = EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes="On time",
        idempotency_key=f"earn-{uuid4()}",
        issued_by=staff_user.id,
    )
    assert event.ledger_transaction_id is not None
    balance = WalletService(db_session).get_balance(wallet.id)
    assert balance == Decimal("5.00")

    tx = LedgerService(db_session).ledger.get_transaction(event.ledger_transaction_id)
    assert tx.status == TransactionStatus.posted
    assert tx.transaction_type == TransactionType.earn
    debits = sum(e.amount for e in tx.entries if e.direction == EntryDirection.debit)
    credits = sum(e.amount for e in tx.entries if e.direction == EntryDirection.credit)
    assert debits == credits == Decimal("5.00")


def test_redeem_transaction(
    student_with_wallet,
    earning_rule,
    staff_user,
    vendor_with_account,
    reward_item,
    db_session,
    system_accounts,
):
    wallet = student_with_wallet.wallet
    EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=f"fund-{uuid4()}",
        issued_by=staff_user.id,
    )
    plain, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    redemption = RedemptionService(db_session).redeem(
        vendor_user_id=vendor_with_account.user_id,
        qr_session_token=plain,
        reward_item_id=reward_item.id,
        idempotency_key=f"redeem-{uuid4()}",
    )
    assert redemption["balance_after"] == Decimal("2.00")
    balance = WalletService(db_session).get_balance(wallet.id)
    assert balance == Decimal("2.00")


def test_insufficient_balance(
    student_with_wallet,
    vendor_with_account,
    reward_item,
    db_session,
    system_accounts,
):
    plain, _ = RedemptionService(db_session).create_qr_session(student_with_wallet.id)
    with pytest.raises(InsufficientCreditsError):
        RedemptionService(db_session).redeem(
            vendor_user_id=vendor_with_account.user_id,
            qr_session_token=plain,
            reward_item_id=reward_item.id,
            idempotency_key=f"fail-{uuid4()}",
        )


def test_idempotency(student_with_wallet, earning_rule, staff_user, db_session, system_accounts):
    key = f"idem-{uuid4()}"
    e1 = EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=key,
        issued_by=staff_user.id,
    )
    e2 = EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=key,
        issued_by=staff_user.id,
    )
    assert e1.ledger_transaction_id == e2.ledger_transaction_id
    balance = WalletService(db_session).get_balance(student_with_wallet.wallet.id)
    assert balance == Decimal("5.00")


def test_debits_equal_credits(student_with_wallet, db_session, system_accounts):
    from app.services.ledger_service import EntrySpec

    wallet = student_with_wallet.wallet
    ledger = LedgerService(db_session)
    pool = ledger.accounts.get_rewards_pool()
    student_acct = ledger.accounts.get_student_wallet_account(wallet.id)
    with pytest.raises(LedgerError, match="must equal credits"):
        ledger.post_transaction(
            transaction_type=TransactionType.adjustment,
            idempotency_key=f"bad-{uuid4()}",
            entries=[
                EntrySpec(pool.id, EntryDirection.debit, Decimal("10.00")),
                EntrySpec(student_acct.id, EntryDirection.credit, Decimal("5.00")),
            ],
        )


def test_transaction_reversal(student_with_wallet, earning_rule, staff_user, db_session, system_accounts):
    wallet = student_with_wallet.wallet
    event = EarningService(db_session).issue_reward(
        student_id=student_with_wallet.id,
        earning_rule_id=earning_rule.id,
        notes=None,
        idempotency_key=f"rev-{uuid4()}",
        issued_by=staff_user.id,
    )
    assert WalletService(db_session).get_balance(wallet.id) == Decimal("5.00")

    reversal = LedgerService(db_session).reverse_transaction(
        event.ledger_transaction_id,
        idempotency_key=f"rev-tx-{uuid4()}",
        created_by=staff_user.id,
    )
    db_session.commit()
    assert WalletService(db_session).get_balance(wallet.id) == Decimal("0.00")
    original = LedgerService(db_session).ledger.get_transaction(event.ledger_transaction_id)
    assert original.status == TransactionStatus.reversed
    assert reversal.transaction_type == TransactionType.reversal
