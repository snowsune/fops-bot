# Just some helper functions to make database access really quick and dirty

import psycopg
import logging
import os


def init_db():
    conn = psycopg.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )

    cur = conn.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS key_value_store (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """
    )
    conn.commit()
    cur.close()
    conn.close()

    return True  # We are ready


def store_key(key, value):
    conn = psycopg.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )

    cur = conn.cursor()
    cur.execute(
        """
    INSERT INTO key_value_store (key, value)
    VALUES (%s, %s)
    ON CONFLICT (key) 
    DO UPDATE SET value = EXCLUDED.value
    """,
        (key, value),
    )
    conn.commit()
    cur.close()
    conn.close()


def retrieve_key(key, default=None):
    conn = psycopg.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )

    cur = conn.cursor()
    cur.execute(
        """
    SELECT value FROM key_value_store WHERE key = %s
    """,
        (key,),
    )
    result = cur.fetchone()
    cur.close()
    conn.close()

    # If key empty/missing
    if not result:
        store_key(key, default)
        logging.warning(f"Inserting default {default} into key {key}")
        return default

    # otherwise return key
    return result[0]
