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
    true,
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
    allow_nsfw = Column(
        Boolean,
        default=False,
        nullable=False,
    )  # Just for NSFW!
    enable_dlp = Column(
        Boolean,
        default=True,
        nullable=False,
    )  # If true, we'll enable the yt-dlp (and other download features)
    twitter_obfuscate = Column(
        Boolean,
        default=False,
        nullable=False,
    )  # If true, we'll enable the twitter obfuscation
    twitter_wrapper = Column(
        String,
        default="fxtwitter.com",
        nullable=False,
    )  # Preferred Twitter mirror domain
    recent_logs = Column(JSON, default=list, nullable=False)

    # Channel configurations
    admin_channel_id = Column(BigInteger, nullable=True)
    ignored_channels = Column(JSON, default=list, nullable=False)

    # Convenience methods (easy to run in cogs)
    def is_frozen(self) -> bool:
        """Check if the guild is frozen."""
        return bool(self.frozen)

    def nsfw(self) -> bool:
        """Check if NSFW content is allowed."""
        return bool(self.allow_nsfw)

    def dlp(self) -> bool:
        """Check if DLP (download) functionality is enabled."""
        return bool(self.enable_dlp)

    def obfuscate_twitter(self) -> bool:
        """Check if Twitter links should be obfuscated (fxtwitter, etc)."""
        return bool(self.twitter_obfuscate)

    def twitter_wrapper_domain(self) -> str:
        """Return the preferred Twitter wrapper domain."""
        return self.twitter_wrapper or "fxtwitter.com"

    def append_log_entry(self, level: str, message: str, limit: int = 10) -> None:
        """
        Appends a log entry to the little store attached for each guild.

        This is just ment to give server owners a quick little view
        of what the bot is up to/any errors or warnings! So only the last
        10 are stored."""

        entries = list(self.recent_logs or [])
        entries.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "message": message,
            }
        )

        if len(entries) > limit:
            entries = entries[-limit:]
        self.recent_logs = entries

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
# Use a single shared engine and session factory to avoid connection exhaustion.
# Previously, get_session() created a NEW engine on every call; each engine has
# its own pool (default 5 + 10 overflow = 15 connections). This caused the bot
# to exhaust connection slots on shared PostgreSQL servers.
_engine = None
_SessionFactory = None


def get_database_url():
    """
    Get the database URL from environment variables or default to SQLite.
    """
    db_url = os.getenv("DATABASE_URL")

    # Use local SQLITE if DATABASE_URL omitted
    if not db_url:
        # Create data directory if it doesn't exist
        import pathlib

        data_dir = pathlib.Path(__file__).parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        db_path = data_dir / "fops_bot.db"
        db_url = f"sqlite:///{db_path}"
        logging.info(f"Using SQLite database for local testing: {db_path}")

    return db_url


def get_engine():
    """Get the single shared SQLAlchemy engine (lazy-initialized)."""
    global _engine
    if _engine is None:
        db_url = get_database_url()
        if db_url.startswith("sqlite:///"):
            _engine = create_engine(
                db_url, connect_args={"check_same_thread": False}
            )
        else:
            # PostgreSQL: limit pool size to avoid exhausting shared server connections.
            # Default would be pool_size=5, max_overflow=10 (15 conns per engine!).
            # With a single shared engine, we cap at 5 connections total.
            _engine = create_engine(
                db_url,
                pool_size=2,
                max_overflow=3,
                pool_pre_ping=True,
            )
    return _engine


def get_session():
    """Get a new session from the shared engine. Always use with a context manager."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory()
