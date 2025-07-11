"""Initial migration

Revision ID: c3fa79a04217
Revises:
Create Date: 2025-05-08 12:04:13.971923

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3fa79a04217"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "guilds",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
    )

    op.create_table(
        "key_value_store",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
    )

    op.create_table(
        "migration_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("migration_name", sa.String(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "features",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_name", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("feature_variables", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.guild_id"]),
        sa.PrimaryKeyConstraint("guild_id", "feature_name"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "migration_log",
        "migration_name",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=False,
    )
    op.alter_column(
        "key_value_store",
        "key",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=False,
    )
    op.alter_column(
        "guilds",
        "name",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.drop_constraint(None, "features", type_="foreignkey")
    op.alter_column(
        "features",
        "feature_name",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=False,
    )
    # ### end Alembic commands ###
