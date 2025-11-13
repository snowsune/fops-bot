"""make guild_id nullable for PM subscriptions

Revision ID: 0b4d25693294
Revises: fa82809801f1
Create Date: 2025-06-23 23:12:33.679520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b4d25693294'
down_revision: Union[str, None] = 'fa82809801f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if we're using SQLite (which doesn't support ALTER COLUMN)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite: Need to recreate the table to change nullable status
        # At this point, the subscriptions table has:
        # id, service_type, user_id, subscribed_at, guild_id, channel_id, 
        # search_criteria, last_reported_id, filters, is_pm
        # (last_ran is added in a later migration)
        
        # Drop the temp table if it exists from a previous failed migration
        op.execute("DROP TABLE IF EXISTS subscriptions_new")
        
        op.create_table(
            "subscriptions_new",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("service_type", sa.String(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("subscribed_at", sa.DateTime(), nullable=False),
            sa.Column("guild_id", sa.BigInteger(), nullable=True),  # Now nullable
            sa.Column("channel_id", sa.BigInteger(), nullable=False),
            sa.Column("search_criteria", sa.String(), nullable=False),
            sa.Column("last_reported_id", sa.String(), nullable=True),
            sa.Column("filters", sa.String(), nullable=True),
            sa.Column("is_pm", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint("id"),
        )

        # Copy data from old table to new table (excluding last_ran - it doesn't exist yet)
        op.execute("""
            INSERT INTO subscriptions_new 
            (id, service_type, user_id, subscribed_at, guild_id, channel_id, 
             search_criteria, last_reported_id, filters, is_pm)
            SELECT id, service_type, user_id, subscribed_at, guild_id, channel_id,
                   search_criteria, last_reported_id, filters, is_pm
            FROM subscriptions
        """)

        # Drop old table and rename new one
        op.drop_table("subscriptions")
        op.rename_table("subscriptions_new", "subscriptions")
    else:
        # PostgreSQL: Simple ALTER COLUMN works
        op.alter_column("subscriptions", "guild_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Check if we're using SQLite
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite: Recreate table with NOT NULL guild_id
        # At downgrade time, last_ran might exist (if we're downgrading from a later migration)
        # But for consistency, we'll only include columns that existed at upgrade time
        
        # Drop the temp table if it exists from a previous failed migration
        op.execute("DROP TABLE IF EXISTS subscriptions_new")
        
        op.create_table(
            "subscriptions_new",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("service_type", sa.String(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("subscribed_at", sa.DateTime(), nullable=False),
            sa.Column("guild_id", sa.BigInteger(), nullable=False),  # NOT NULL again
            sa.Column("channel_id", sa.BigInteger(), nullable=False),
            sa.Column("search_criteria", sa.String(), nullable=False),
            sa.Column("last_reported_id", sa.String(), nullable=True),
            sa.Column("filters", sa.String(), nullable=True),
            sa.Column("is_pm", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint("id"),
        )

        # Copy data, filtering out rows with NULL guild_id (they shouldn't exist in old schema anyway)
        op.execute("""
            INSERT INTO subscriptions_new 
            (id, service_type, user_id, subscribed_at, guild_id, channel_id, 
             search_criteria, last_reported_id, filters, is_pm)
            SELECT id, service_type, user_id, subscribed_at, guild_id, channel_id,
                   search_criteria, last_reported_id, filters, is_pm
            FROM subscriptions
            WHERE guild_id IS NOT NULL
        """)

        op.drop_table("subscriptions")
        op.rename_table("subscriptions_new", "subscriptions")
    else:
        # PostgreSQL: Simple ALTER COLUMN works
        op.alter_column("subscriptions", "guild_id", existing_type=sa.BigInteger(), nullable=False)
