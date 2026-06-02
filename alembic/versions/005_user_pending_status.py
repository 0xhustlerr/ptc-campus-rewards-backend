"""Add pending status for user approval workflow."""

from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'pending'")


def downgrade() -> None:
    # Postgres enum values are append-only in-place; keep value for safe downgrade.
    pass
