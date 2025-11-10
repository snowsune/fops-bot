"""Add twitter wrapper column to guilds

Revision ID: e1c5ab7d6d4f
Revises: c72a1dcb408e
Create Date: 2025-11-10 22:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1c5ab7d6d4f"
down_revision: Union[str | None] = "3c79d62144a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "twitter_wrapper",
            sa.String(),
            server_default="fxtwitter.com",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("guilds", "twitter_wrapper")
