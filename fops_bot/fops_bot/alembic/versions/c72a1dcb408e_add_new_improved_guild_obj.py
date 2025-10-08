"""Add new improved guild obj

Revision ID: c72a1dcb408e
Revises: a1ae352b0e46
Create Date: 2025-10-08 13:00:27.617630

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c72a1dcb408e"
down_revision: Union[str, None] = "a1ae352b0e46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns with server defaults for existing rows
    op.add_column(
        "guilds",
        sa.Column("frozen", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "guilds",
        sa.Column("allow_nsfw", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "guilds",
        sa.Column("enable_dlp", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "guilds", sa.Column("admin_channel_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "guilds",
        sa.Column("ignored_channels", sa.JSON(), server_default="[]", nullable=False),
    )

    # Drop legacy features table (replaced by discrete columns)
    op.drop_table("features")


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate features table
    op.create_table(
        "features",
        sa.Column("guild_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("feature_name", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("enabled", sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column("feature_variables", sa.TEXT(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["guild_id"], ["guilds.guild_id"], name="features_guild_id_fkey"
        ),
        sa.PrimaryKeyConstraint("guild_id", "feature_name", name="features_pkey"),
    )

    # Remove the new guild columns
    op.drop_column("guilds", "ignored_channels")
    op.drop_column("guilds", "admin_channel_id")
    op.drop_column("guilds", "enable_dlp")
    op.drop_column("guilds", "allow_nsfw")
    op.drop_column("guilds", "frozen")
