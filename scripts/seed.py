"""
Seed default earning rules, reward items, and system ledger accounts.

Usage:
  python -m scripts.seed
"""

from decimal import Decimal

from app.core.database import SessionLocal
from app.models.earning_rule import EarningRule
from app.models.enums import RewardCategory
from app.models.reward_item import RewardItem
from app.repositories.earning_rule import EarningRuleRepository
from app.repositories.reward_item import RewardItemRepository
from app.services.system_accounts_service import SystemAccountsService

EARNING_RULES = [
    ("ATTENDANCE_ON_TIME", "On-time attendance", Decimal("1.00")),
    ("HAIRCUT_COMPLETED", "Haircut completed", Decimal("2.00")),
    ("BEARD_TRIM", "Beard trim", Decimal("1.00")),
    ("SANITATION_PASSED", "Clean station / sanitation passed", Decimal("1.00")),
    ("QUIZ_PASSED", "Quiz passed", Decimal("3.00")),
    ("PEER_MENTORSHIP", "Peer mentorship", Decimal("2.00")),
    ("PERFECT_ATTENDANCE_WEEK", "Perfect attendance week", Decimal("10.00")),
]

REWARD_ITEMS = [
    ("Sandwich", RewardCategory.food_truck, Decimal("8.00")),
    ("Drink", RewardCategory.food_truck, Decimal("3.00")),
    ("Clipper Guards", RewardCategory.school_supplies, Decimal("20.00")),
    ("Comb", RewardCategory.school_supplies, Decimal("5.00")),
    ("VIP Workshop Seat", RewardCategory.student_perks, Decimal("40.00")),
]


def seed() -> None:
    db = SessionLocal()
    try:
        SystemAccountsService(db).ensure_system_accounts()

        rules_repo = EarningRuleRepository(db)
        for code, name, amount in EARNING_RULES:
            if rules_repo.get_by_code(code):
                continue
            rules_repo.create(
                EarningRule(
                    code=code,
                    name=name,
                    token_amount=amount,
                    requires_note=code == "SANITATION_PASSED",
                    active=True,
                )
            )

        items_repo = RewardItemRepository(db)
        existing_names = {i.name for i in items_repo.list_all()}
        for name, category, price in REWARD_ITEMS:
            if name in existing_names:
                continue
            items_repo.create(
                RewardItem(
                    name=name,
                    category=category,
                    price_tokens=price,
                    active=True,
                )
            )

        db.commit()
        print("Seed completed: system accounts, earning rules, reward items.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
