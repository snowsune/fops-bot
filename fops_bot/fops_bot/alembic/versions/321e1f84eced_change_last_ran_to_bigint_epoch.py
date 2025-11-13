"""change last_ran to bigint epoch

Revision ID: 321e1f84eced
Revises: f4378b1068d1
Create Date: 2025-06-25 11:59:09.831081

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "321e1f84eced"
down_revision: Union[str, None] = "f4378b1068d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if we're using SQLite (which doesn't support ALTER COLUMN)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite: Need to recreate the table to change column type
        # Drop temp table if exists from previous failed migration
        op.execute("DROP TABLE IF EXISTS subscriptions_new")

        # Create new table with BigInteger last_ran
        op.create_table(
            "subscriptions_new",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("service_type", sa.String(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("subscribed_at", sa.DateTime(), nullable=False),
            sa.Column("guild_id", sa.BigInteger(), nullable=True),
            sa.Column("channel_id", sa.BigInteger(), nullable=False),
            sa.Column("search_criteria", sa.String(), nullable=False),
            sa.Column("last_reported_id", sa.String(), nullable=True),
            sa.Column("filters", sa.String(), nullable=True),
            sa.Column("is_pm", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_ran", sa.BigInteger(), nullable=True),  # Changed to BigInteger
            sa.PrimaryKeyConstraint("id"),
        )

        # Copy data, converting DateTime to epoch timestamp (Unix timestamp)
        # SQLite stores DateTime as strings, so we use strftime to convert to epoch
        op.execute("""
            INSERT INTO subscriptions_new 
            (id, service_type, user_id, subscribed_at, guild_id, channel_id, 
             search_criteria, last_reported_id, filters, is_pm, last_ran)
            SELECT 
                id, service_type, user_id, subscribed_at, guild_id, channel_id,
                search_criteria, last_reported_id, filters, is_pm,
                CASE 
                    WHEN last_ran IS NULL THEN NULL
                    ELSE CAST(strftime('%s', last_ran) AS INTEGER)
                END
            FROM subscriptions
        """)

        # Drop old table and rename new one
        op.drop_table("subscriptions")
        op.rename_table("subscriptions_new", "subscriptions")
    else:
        # PostgreSQL: Use ALTER COLUMN with USING clause
        op.alter_column(
            "subscriptions",
            "last_ran",
            existing_type=postgresql.TIMESTAMP(),
            type_=sa.BigInteger(),
            existing_nullable=True,
            postgresql_using="EXTRACT(EPOCH FROM last_ran)::bigint",
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Check if we're using SQLite
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite: Recreate table with DateTime last_ran
        # Drop temp table if exists from previous failed migration
        op.execute("DROP TABLE IF EXISTS subscriptions_new")

        op.create_table(
            "subscriptions_new",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("service_type", sa.String(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("subscribed_at", sa.DateTime(), nullable=False),
            sa.Column("guild_id", sa.BigInteger(), nullable=True),
            sa.Column("channel_id", sa.BigInteger(), nullable=False),
            sa.Column("search_criteria", sa.String(), nullable=False),
            sa.Column("last_reported_id", sa.String(), nullable=True),
            sa.Column("filters", sa.String(), nullable=True),
            sa.Column("is_pm", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_ran", sa.DateTime(), nullable=True),  # Changed back to DateTime
            sa.PrimaryKeyConstraint("id"),
        )

        # Copy data, converting epoch timestamp to DateTime
        op.execute("""
            INSERT INTO subscriptions_new 
            (id, service_type, user_id, subscribed_at, guild_id, channel_id, 
             search_criteria, last_reported_id, filters, is_pm, last_ran)
            SELECT 
                id, service_type, user_id, subscribed_at, guild_id, channel_id,
                search_criteria, last_reported_id, filters, is_pm,
                CASE 
                    WHEN last_ran IS NULL THEN NULL
                    ELSE datetime(last_ran, 'unixepoch')
                END
            FROM subscriptions
        """)

        op.drop_table("subscriptions")
        op.rename_table("subscriptions_new", "subscriptions")
    else:
        # PostgreSQL: Use ALTER COLUMN
        op.alter_column(
            "subscriptions",
            "last_ran",
            existing_type=sa.BigInteger(),
            type_=postgresql.TIMESTAMP(),
            existing_nullable=True,
        )
