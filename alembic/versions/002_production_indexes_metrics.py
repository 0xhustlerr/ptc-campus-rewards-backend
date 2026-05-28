"""Production indexes and admin metrics snapshots.

Revision ID: 002
Revises: 001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_metrics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_type", sa.String(64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_admin_metrics_type_date", "admin_metrics_snapshots", ["snapshot_type", "snapshot_date"])

    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])
    op.create_index("ix_ledger_transactions_created_at", "ledger_transactions", ["created_at"])
    op.create_index("ix_earning_events_student_rule", "earning_events", ["student_id", "rule_id"])
    op.create_index("ix_redemptions_vendor_created", "redemptions", ["vendor_id", "created_at"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", "audit_logs")
    op.drop_index("ix_redemptions_vendor_created", "redemptions")
    op.drop_index("ix_earning_events_student_rule", "earning_events")
    op.drop_index("ix_ledger_transactions_created_at", "ledger_transactions")
    op.drop_index("ix_ledger_entries_account_id", "ledger_entries")
    op.drop_index("ix_admin_metrics_type_date", "admin_metrics_snapshots")
    op.drop_table("admin_metrics_snapshots")
