"""Redemption idempotency and receipt balance columns."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_redemption_idempotency"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "redemptions",
        sa.Column("idempotency_key", sa.String(128), nullable=True),
    )
    op.add_column(
        "redemptions",
        sa.Column("balance_before", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "redemptions",
        sa.Column("balance_after", sa.Numeric(18, 2), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE redemptions SET idempotency_key = 'legacy-' || id::text WHERE idempotency_key IS NULL"
        )
    )
    op.alter_column("redemptions", "idempotency_key", nullable=False)
    op.create_index("ix_redemptions_idempotency_key", "redemptions", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_redemptions_idempotency_key", table_name="redemptions")
    op.drop_column("redemptions", "balance_after")
    op.drop_column("redemptions", "balance_before")
    op.drop_column("redemptions", "idempotency_key")
