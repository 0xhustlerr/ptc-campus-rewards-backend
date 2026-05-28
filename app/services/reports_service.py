"""Admin reporting — PTC Credits aggregates for dashboards."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.earning_event import EarningEvent
from app.models.earning_rule import EarningRule
from app.models.enums import (
    EarningEventStatus,
    EntryDirection,
    RedemptionStatus,
    TransactionStatus,
    TransactionType,
    WalletStatus,
)
from app.models.ledger import LedgerEntry, LedgerTransaction
from app.models.ledger_account import LedgerAccount
from app.models.redemption import Redemption
from app.models.reward_item import RewardItem
from app.models.student import Student
from app.models.vendor import Vendor
from app.models.wallet import Wallet
from app.repositories.ledger import LedgerRepository
from app.repositories.ledger_account import LedgerAccountRepository


class ReportsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.ledger = LedgerRepository(db)
        self.accounts = LedgerAccountRepository(db)

    def overview(self) -> dict:
        today = datetime.now(UTC).date()
        students = self.db.scalars(select(Student)).all()
        wallets = self.db.scalars(select(Wallet)).all()
        active_wallets = sum(1 for w in wallets if w.status == WalletStatus.active)

        total_issued = self._sum_by_tx_type(TransactionType.earn) + self._sum_by_tx_type(
            TransactionType.bonus
        )
        total_redeemed = self._sum_by_tx_type(TransactionType.redeem)
        outstanding = self._outstanding_balance()

        redemptions_today = self.db.scalar(
            select(func.count())
            .select_from(Redemption)
            .where(
                func.date(Redemption.created_at) == today,
                Redemption.status == RedemptionStatus.completed,
            )
        )
        txs_today = self.db.scalar(
            select(func.count())
            .select_from(LedgerTransaction)
            .where(
                func.date(LedgerTransaction.created_at) == today,
                LedgerTransaction.status == TransactionStatus.posted,
            )
        )

        most_active = self._most_active_student_name()

        return {
            "total_students": len(students),
            "active_wallets": active_wallets,
            "total_ptc_issued": total_issued,
            "total_ptc_redeemed": total_redeemed,
            "outstanding_ptc_balance": outstanding,
            "redemptions_today": int(redemptions_today or 0),
            "transactions_today": int(txs_today or 0),
            "most_active_student": most_active,
        }

    def token_velocity(self, days: int = 7) -> dict:
        since = datetime.now(UTC) - timedelta(days=days)
        rows = self.db.scalars(
            select(LedgerTransaction).where(LedgerTransaction.created_at >= since)
        ).all()
        daily: dict[str, dict] = {}
        for tx in rows:
            if tx.status not in (TransactionStatus.posted, TransactionStatus.reversed):
                continue
            day = tx.created_at.date().isoformat()
            if day not in daily:
                daily[day] = {"issued": Decimal("0"), "redeemed": Decimal("0"), "count": 0}
            amount = sum(e.amount for e in tx.entries if e.direction == EntryDirection.debit)
            daily[day]["count"] += 1
            if tx.transaction_type in (TransactionType.earn, TransactionType.bonus):
                daily[day]["issued"] += amount
            elif tx.transaction_type == TransactionType.redeem:
                daily[day]["redeemed"] += amount

        return {
            "days": days,
            "series": [
                {
                    "date": d,
                    "issued": str(v["issued"]),
                    "redeemed": str(v["redeemed"]),
                    "transaction_count": v["count"],
                }
                for d, v in sorted(daily.items())
            ],
        }

    def earned_by_rule(self) -> list[dict]:
        stmt = (
            select(EarningRule.name, func.sum(EarningEvent.amount), func.count())
            .join(EarningEvent, EarningEvent.rule_id == EarningRule.id)
            .where(EarningEvent.status == EarningEventStatus.posted)
            .group_by(EarningRule.name)
            .order_by(func.sum(EarningEvent.amount).desc())
        )
        rows = self.db.execute(stmt).all()
        return [
            {"rule": name, "total_ptc": str(total or 0), "event_count": count}
            for name, total, count in rows
        ]

    def redeemed_by_category(self) -> list[dict]:
        stmt = (
            select(RewardItem.category, func.sum(Redemption.amount_tokens), func.count())
            .join(Redemption, Redemption.reward_item_id == RewardItem.id)
            .where(Redemption.status == RedemptionStatus.completed)
            .group_by(RewardItem.category)
        )
        rows = self.db.execute(stmt).all()
        return [
            {"category": cat.value, "total_ptc": str(total or 0), "redemption_count": count}
            for cat, total, count in rows
        ]

    def top_students(self, limit: int = 10) -> list[dict]:
        students = self.db.scalars(select(Student)).all()
        ranked: list[tuple[str, Decimal, int]] = []
        for s in students:
            if not s.wallet:
                continue
            acct = self.accounts.get_student_wallet_account(s.wallet.id)
            if not acct:
                continue
            balance = self.ledger.account_balance(acct.id)
            tx_count = self.ledger.count_wallet_transactions(s.wallet.id)
            ranked.append((s.full_name, balance, tx_count))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return [
            {"student_name": name, "balance": str(bal), "transaction_count": cnt}
            for name, bal, cnt in ranked[:limit]
        ]

    def vendor_summary(self) -> list[dict]:
        vendors = self.db.scalars(select(Vendor)).all()
        result = []
        for v in vendors:
            total = self.db.scalar(
                select(func.coalesce(func.sum(Redemption.amount_tokens), 0)).where(
                    Redemption.vendor_id == v.id,
                    Redemption.status == RedemptionStatus.completed,
                )
            )
            count = self.db.scalar(
                select(func.count())
                .select_from(Redemption)
                .where(
                    Redemption.vendor_id == v.id,
                    Redemption.status == RedemptionStatus.completed,
                )
            )
            result.append(
                {
                    "vendor_id": str(v.id),
                    "vendor_name": v.name,
                    "vendor_type": v.vendor_type.value,
                    "total_ptc_redeemed": str(total or 0),
                    "redemption_count": int(count or 0),
                }
            )
        return result

    def daily_activity_summary(self) -> dict:
        today = date.today()
        overview = self.overview()
        top_rule = self.earned_by_rule()
        top_item_stmt = (
            select(RewardItem.name, func.count())
            .join(Redemption)
            .where(func.date(Redemption.created_at) == today)
            .group_by(RewardItem.name)
            .order_by(func.count().desc())
            .limit(1)
        )
        top_item_row = self.db.execute(top_item_stmt).first()
        return {
            "date": today.isoformat(),
            "total_issued_today": overview.get("total_ptc_issued"),
            "total_redeemed_today": overview.get("total_ptc_redeemed"),
            "active_students": overview["total_students"],
            "top_earning_rule": top_rule[0] if top_rule else None,
            "top_reward_item": top_item_row[0] if top_item_row else None,
        }

    def _sum_by_tx_type(self, tx_type: TransactionType) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(LedgerEntry.amount), 0))
            .join(LedgerTransaction)
            .where(
                LedgerTransaction.transaction_type == tx_type,
                LedgerTransaction.status.in_(
                    [TransactionStatus.posted, TransactionStatus.reversed]
                ),
                LedgerEntry.direction == EntryDirection.debit,
            )
        )
        return Decimal(str(self.db.scalar(stmt) or 0))

    def _outstanding_balance(self) -> Decimal:
        accounts = self.db.scalars(
            select(LedgerAccount).where(LedgerAccount.wallet_id.isnot(None))
        ).all()
        return sum(self.ledger.account_balance(a.id) for a in accounts)

    def _most_active_student_name(self) -> str | None:
        students = self.db.scalars(select(Student)).all()
        best_name = None
        best_count = -1
        for s in students:
            if not s.wallet:
                continue
            cnt = self.ledger.count_wallet_transactions(s.wallet.id)
            if cnt > best_count:
                best_count = cnt
                best_name = s.full_name
        return best_name
