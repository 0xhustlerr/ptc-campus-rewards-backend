"""Ledger integrity constraints."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003_redemption_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_ledger_entries_amount_positive",
        "ledger_entries",
        "amount > 0",
    )
    op.create_index(
        "uq_ledger_accounts_wallet_account_type",
        "ledger_accounts",
        ["wallet_id", "account_type"],
        unique=True,
        postgresql_where=sa.text("wallet_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ledger_accounts_wallet_account_type", table_name="ledger_accounts")
    op.drop_constraint("ck_ledger_entries_amount_positive", "ledger_entries", type_="check")
