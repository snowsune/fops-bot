import os
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

    features = relationship("Feature", back_populates="guild")


class Feature(Base):
    __tablename__ = "features"

    guild_id = Column(BigInteger, ForeignKey("guilds.guild_id"), primary_key=True)
    feature_name = Column(String, primary_key=True)
    enabled = Column(Boolean)
    feature_variables = Column(Text)

    guild = relationship("Guild", back_populates="features")


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
    guild_id = Column(BigInteger, nullable=False)  # Discord guild ID
    channel_id = Column(BigInteger, nullable=False)  # Discord channel ID
    search_criteria = Column(String, nullable=False)  # Username or search string
    last_reported_id = Column(String, nullable=True)  # Last reported post/submission ID


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
