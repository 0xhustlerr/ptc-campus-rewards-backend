"""Prevent duplicate system and vendor ledger accounts.

The partial unique index in migration 004 only covers wallet accounts, leaving
rewards_pool / system_adjustment (singleton system accounts) and per-vendor
revenue accounts unprotected. Concurrent ensure_* calls (seed + worker, or two
Celery tasks) could create duplicates, after which balance reads split
nondeterministically across rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # At most one system account (rewards_pool / system_adjustment) per type.
    op.create_index(
        "uq_ledger_accounts_system_account_type",
        "ledger_accounts",
        ["account_type"],
        unique=True,
        postgresql_where=sa.text("wallet_id IS NULL AND vendor_id IS NULL"),
    )
    # At most one revenue account per vendor.
    op.create_index(
        "uq_ledger_accounts_vendor_account_type",
        "ledger_accounts",
        ["vendor_id", "account_type"],
        unique=True,
        postgresql_where=sa.text("vendor_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ledger_accounts_vendor_account_type", table_name="ledger_accounts")
    op.drop_index("uq_ledger_accounts_system_account_type", table_name="ledger_accounts")
