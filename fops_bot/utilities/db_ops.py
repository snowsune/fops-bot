import logging
from typing import Optional, List, Dict, Any, cast
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..models import Guild, Feature, KeyValueStore, get_session


def add_guild(guild_id: int, guild_name: str) -> None:
    """Add or update a guild in the database."""
    with get_session() as session:
        guild = session.get(Guild, guild_id)
        if guild:
            guild.name = guild_name  # type: ignore
        else:
            guild = Guild(guild_id=guild_id, name=guild_name)
            session.add(guild)
        session.commit()


def remove_guild(guild_id: int) -> None:
    """Remove a guild from the database."""
    with get_session() as session:
        guild = session.get(Guild, guild_id)
        if guild:
            session.delete(guild)
            session.commit()


def get_all_guilds() -> List[Guild]:
    """Get all guilds from the database."""
    with get_session() as session:
        return list(session.scalars(select(Guild)))


def is_feature_enabled(guild_id: int, feature_name: str, default: bool = False) -> bool:
    """Check if a feature is enabled for a guild."""
    with get_session() as session:
        stmt = select(Feature).where(
            Feature.guild_id == guild_id, Feature.feature_name == feature_name
        )
        feature = session.scalar(stmt)

        if feature is None:
            # Create feature with default state
            feature = Feature(
                guild_id=guild_id, feature_name=feature_name, enabled=default
            )
            session.add(feature)
            session.commit()
            return default

        return cast(bool, feature.enabled)


def set_feature_state(
    guild_id: int,
    feature_name: str,
    enabled: bool,
    feature_variables: Optional[str] = None,
) -> None:
    """Set the state and variables for a feature in a guild."""
    with get_session() as session:
        stmt = select(Feature).where(
            Feature.guild_id == guild_id, Feature.feature_name == feature_name
        )
        feature = session.scalar(stmt)

        if feature:
            feature.enabled = enabled  # type: ignore
            if feature_variables is not None:
                feature.feature_variables = feature_variables  # type: ignore
        else:
            feature = Feature(
                guild_id=guild_id,
                feature_name=feature_name,
                enabled=enabled,
                feature_variables=feature_variables,
            )
            session.add(feature)

        session.commit()


def get_feature_data(guild_id: int, feature_name: str) -> Optional[Dict[str, Any]]:
    """Get feature data for a guild."""
    with get_session() as session:
        stmt = select(Feature).where(
            Feature.guild_id == guild_id, Feature.feature_name == feature_name
        )
        feature = session.scalar(stmt)

        if feature:
            return {
                "enabled": cast(bool, feature.enabled),
                "feature_variables": cast(str, feature.feature_variables),
            }
        return None


def get_guilds_with_feature_enabled(feature_name: str) -> List[int]:
    """Get all guild IDs where a feature is enabled."""
    with get_session() as session:
        stmt = select(Feature.guild_id).where(
            Feature.feature_name == feature_name, Feature.enabled == True
        )
        return [row[0] for row in session.execute(stmt)]


# === KeyValueStore ===
# Methods for dealing with the KeyValueStore table


def store_key(key: str, value: str) -> None:
    """Store a key-value pair."""
    with get_session() as session:
        kv = session.get(KeyValueStore, key)
        if kv:
            kv.value = value  # type: ignore
        else:
            kv = KeyValueStore(key=key, value=value)
            session.add(kv)
        session.commit()


def retrieve_key(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve a value by key."""
    with get_session() as session:
        kv = session.get(KeyValueStore, key)
        if not kv:
            if default is not None:
                store_key(key, default)
                logging.warning(f"Inserting default {default} into key {key}")
            return default
        return cast(str, kv.value)
