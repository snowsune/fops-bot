"""Add recent_logs to guilds

Revision ID: 1a2b3c4d5e6f
Revises: e1c5ab7d6d4f
Create Date: 2025-11-10 22:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1a2b3c4d5e6f"
down_revision: Union[str | None] = "e1c5ab7d6d4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column("recent_logs", sa.JSON(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("guilds", "recent_logs")
