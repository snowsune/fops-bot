import os
import logging
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    BigInteger,
    DateTime,
    Text,
    ForeignKey,
    create_engine,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from datetime import timezone


Base = declarative_base()


class Guild(Base):
    __tablename__ = "guilds"

    guild_id = Column(BigInteger, primary_key=True)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    name = Column(String)

    # Admin flags
    frozen = Column(Boolean, default=False, nullable=False)

    # Feature flags
    allow_nsfw = Column(Boolean, default=False, nullable=False)
    enable_dlp = Column(Boolean, default=False, nullable=False)

    # Channel configurations
    admin_channel_id = Column(BigInteger, nullable=True)
    ignored_channels = Column(JSON, default=list, nullable=False)

    # Convenience methods (easy to run in cogs)
    def is_frozen(self) -> bool:
        """Check if the guild is frozen."""
        logging.warning(f"Guild {self.guild_id} is frozen!")
        return bool(self.frozen)

    def nsfw(self) -> bool:
        """Check if NSFW content is allowed."""
        return bool(self.allow_nsfw)

    def dlp(self) -> bool:
        """Check if DLP (download) functionality is enabled."""
        return bool(self.enable_dlp)

    def admin_channel(self) -> int | None:
        """Get the admin channel ID."""
        return self.admin_channel_id

    def is_channel_ignored(self, ctx) -> bool:
        """
        Check if a channel is in the ignored list.
        """

        if not self.ignored_channels:
            return False
        channel_id = ctx.channel.id if hasattr(ctx, "channel") else ctx
        return channel_id in self.ignored_channels

    def get_ignored_channels(self) -> list[int]:
        """Get list of ignored channel IDs."""
        return list(self.ignored_channels) if self.ignored_channels else []


class KeyValueStore(Base):
    __tablename__ = "key_value_store"

    key = Column(String, primary_key=True)
    value = Column(Text)


class MigrationLog(Base):
    __tablename__ = "migration_log"

    id = Column(Integer, primary_key=True)
    migration_name = Column(String, nullable=False)
    applied_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_type = Column(String, nullable=False)  # e.g., 'FurAffinity', 'booru', 'e6'
    user_id = Column(BigInteger, nullable=False)  # Discord user ID
    subscribed_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    guild_id = Column(BigInteger, nullable=True)  # Discord guild ID (nullable for PM)
    channel_id = Column(BigInteger, nullable=False)  # Discord channel ID
    search_criteria = Column(String, nullable=False)  # Username or search string
    last_reported_id = Column(String, nullable=True)  # Last reported post/submission ID
    filters = Column(String, nullable=True)  # Tag filters or exclusion criteria
    is_pm = Column(Boolean, nullable=False, default=False)  # Whether to deliver via PM
    last_ran = Column(
        BigInteger, nullable=True, default=None
    )  # Last time this subscription was checked (epoch seconds)


class Hole(Base):
    __tablename__ = "holes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Where the hole comes from
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)

    # Where the hole is forwarded to
    forwarded_channel_id = Column(BigInteger, nullable=False)
    is_pm = Column(Boolean, nullable=False, default=False)
    anonymize = Column(Boolean, nullable=False, default=False)


class HoleUserColor(Base):
    __tablename__ = "hole_user_colors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    color = Column(String, nullable=False)
    __table_args__ = (
        # Ensure unique color per user per guild
        {},
    )


# Database connection setup
def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set!")
    return create_engine(db_url)


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
