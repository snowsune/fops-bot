import logging
from typing import Optional, List, Dict, Any, cast
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from fops_bot.models import Guild, KeyValueStore, get_session


def is_feature_enabled(
    guild_id: int, feature_name: str, default: bool = False, guild_name: str = ""
) -> bool:
    """Legacy!"""

    logging.warning("is_feature_enabled is deprecated. Use is_nsfw_allowed instead.")
    return False


def set_feature_state(
    guild_id: int,
    feature_name: str,
    enabled: bool,
    feature_variables: Optional[str] = None,
    guild_name: str = "",
) -> None:
    """Legacy!"""

    logging.warning("set_feature_state is deprecated. Use set_nsfw_allowed instead.")
    return


def get_feature_data(guild_id: int, feature_name: str) -> Optional[Dict[str, Any]]:
    """Legacy!"""

    logging.warning("get_feature_data is deprecated. Use get_nsfw_allowed instead.")
    return None


def get_guilds_with_feature_enabled(feature_name: str) -> List[int]:
    """Legacy!"""

    logging.warning(
        "get_guilds_with_feature_enabled is deprecated. Use get_guilds_with_nsfw_allowed instead."
    )
    return []


# === KeyValueStore ===
# Methods for dealing with the KeyValueStore table


def store_key(key: str, value) -> None:
    """Store a key-value pair as a string."""
    with get_session() as session:
        kv = session.get(KeyValueStore, key)
        if kv:
            kv.value = str(value)
        else:
            kv = KeyValueStore(key=key, value=str(value))
            session.add(kv)
        session.commit()


def retrieve_key(key: str, default: str) -> str:
    """Retrieve a value by key as a string. Always returns a string."""
    with get_session() as session:
        kv = session.get(KeyValueStore, key)
        if not kv or kv.value is None:
            store_key(key, default)
            return str(default)
        return str(kv.value)


def store_key_number(key: str, value: int) -> None:
    store_key(key, str(value))


def retrieve_key_number(key: str, default: int) -> int:
    value = retrieve_key(key, str(default))
    try:
        return int(value)
    except Exception:
        return default


def store_number(key: str, value: int) -> None:
    """Store a numeric value."""
    store_key(key, str(value))


def retrieve_number(key: str, default: int = 0) -> int:
    """Retrieve a numeric value by key."""
    value = retrieve_key(key, str(default))
    return int(value) if value is not None else default


def get_db_info() -> str:
    """Return the database version string."""
    with get_session() as session:
        result = session.execute(text("SELECT version();"))
        version = result.scalar()
        return str(version)


async def check_nsfw_allowed(ctx) -> bool:
    logging.warning("Use NSFW check on guild instead")
    return False
