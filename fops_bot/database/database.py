import os
import logging

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base


# Base is declarativebase
Base = declarative_base()

# (Same as in env.py)
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5438")
DB_NAME = os.getenv("DB_NAME", "fops_bot_db")

db_url = f"postgresql+psycopg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Initialize the engine and session
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)


# Define the KeyValueStore model (replacement for old keyvaluestore)
class KeyValueStore(Base):
    __tablename__ = "key_value_store"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)

    @staticmethod
    def store_key(session, key, value):
        entry = session.query(KeyValueStore).filter_by(key=key).first()
        if entry:
            entry.value = value
        else:
            entry = KeyValueStore(key=key, value=value)
            session.add(entry)
        session.commit()

    @staticmethod
    def retrieve_key(session, key, default=None):
        entry = session.query(KeyValueStore).filter_by(key=key).first()
        if not entry:
            logging.warning(f"Inserting default {default} into key {key}")
            KeyValueStore.store_key(session, key, default)
            return default
        return entry.value


# Guild and Feature Models
class Guild(Base):
    __tablename__ = "guilds"

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    features = relationship(
        "Feature", back_populates="guild", cascade="all, delete-orphan"
    )

    def add_or_update_feature(self, session, feature_name, enabled=True, data=None):
        feature = next((f for f in self.features if f.name == feature_name), None)
        if feature:
            feature.enabled = enabled
            feature.data = data
        else:
            feature = Feature(name=feature_name, enabled=enabled, data=data, guild=self)
            self.features.append(feature)
        session.commit()

    def get_all_features(self):
        return {feature.name: feature.enabled for feature in self.features}


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    data = Column(Text)  # JSON or stringified list (e.g., channels/users)
    guild_id = Column(Integer, ForeignKey("guilds.id"))
    guild = relationship("Guild", back_populates="features")


# Utility Functions
def get_or_create_guild(session, guild_id, guild_name):
    guild = session.query(Guild).filter_by(guild_id=guild_id).first()
    if not guild:
        guild = Guild(guild_id=guild_id, name=guild_name)
        session.add(guild)
        session.commit()
    return guild


def set_feature(session, guild_id, feature_name, enabled=True, data=None):
    guild = get_or_create_guild(session, guild_id, "Unknown Guild")
    guild.add_or_update_feature(session, feature_name, enabled, data)


def get_all_features(session, guild_id):
    guild = session.query(Guild).filter_by(guild_id=guild_id).first()
    if not guild:
        return {}
    return guild.get_all_features()
