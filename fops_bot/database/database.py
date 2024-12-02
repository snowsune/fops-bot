from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import os
import logging

# Base is declarativebase
Base = declarative_base()

# Replaces the old method of db env conn
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot_database.db")

# Initialize the engine and session
engine = create_engine(DATABASE_URL)
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
