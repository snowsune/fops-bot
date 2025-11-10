from sqlalchemy import text

from fops_bot.models import KeyValueStore, get_session


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
