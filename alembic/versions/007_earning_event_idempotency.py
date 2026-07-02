"""Add idempotency_key to earning_events for approval-path dedupe."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "earning_events",
        sa.Column("idempotency_key", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_earning_events_idempotency_key",
        "earning_events",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_earning_events_idempotency_key", table_name="earning_events")
    op.drop_column("earning_events", "idempotency_key")
