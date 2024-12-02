import os
import sqlalchemy

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from fops_bot.database.database import Base

import logging

logging.basicConfig(level=logging.DEBUG)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Dynamically build the SQLAlchemy URL (needed because we dont always dev with env vars)
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5438")
DB_NAME = os.getenv("DB_NAME", "fops_bot_db")

db_url = f"postgresql+psycopg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
config.set_main_option("sqlalchemy.url", db_url)

logging.debug("Final DB URL: %s", db_url)

# Model metadata object
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # Log the connection URL for debugging
    logging.debug("Database URL: %s", config.get_main_option("sqlalchemy.url"))

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Log the database server version for verification
        server_version = connection.execute(
            sqlalchemy.text("SELECT version();")
        ).scalar()
        logging.debug("Connected to DB server version: %s", server_version)

        # Set the statement timeout
        connection.execute(sqlalchemy.text("SET statement_timeout = '5s'"))

        # Configure for migrations
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    logging.warning("Alembic in offline mode!")
    run_migrations_offline()
else:
    run_migrations_online()
