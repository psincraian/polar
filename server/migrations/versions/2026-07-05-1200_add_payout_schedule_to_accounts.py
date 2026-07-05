"""Add payout schedule columns to accounts

Revision ID: 3b2f7a9c1e04
Revises: a7f3e1c20b94
Create Date: 2026-07-05 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# Polar Custom Imports

# revision identifiers, used by Alembic.
revision = "3b2f7a9c1e04"
down_revision = "a7f3e1c20b94"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "payout_schedule",
            sa.String(),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column("payout_schedule_weekday", sa.Integer(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("payout_schedule_day_of_month", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "payout_schedule_day_of_month")
    op.drop_column("accounts", "payout_schedule_weekday")
    op.drop_column("accounts", "payout_schedule")
