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


# Database connection setup
def get_engine():
    return create_engine(
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
