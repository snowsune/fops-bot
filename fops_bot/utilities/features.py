import logging
from .database import getCur


# Guilds management
def add_guild(guild_id, guild_name):
    cur, conn = getCur()

    cur.execute(
        """
        INSERT INTO guilds (guild_id, name) VALUES (%s, %s)
        ON CONFLICT (guild_id) DO UPDATE SET name = EXCLUDED.name;
    """,
        (guild_id, guild_name),
    )

    conn.commit()
    cur.close()
    conn.close()


def remove_guild(guild_id):
    cur, conn = getCur()

    cur.execute("DELETE FROM guilds WHERE guild_id = %s;", (guild_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_all_guilds():
    cur, conn = getCur()

    cur.execute("SELECT * FROM guilds;")
    result = cur.fetchall()

    cur.close()
    conn.close()
    return result


# Feature management
def is_feature_enabled(guild_id, feature_name, default=False):
    cur, conn = getCur()

    cur.execute(
        """
        SELECT enabled FROM features WHERE guild_id = %s AND feature_name = %s;
    """,
        (guild_id, feature_name),
    )
    result = cur.fetchone()

    if result is None:
        logging.info(
            f"Feature '{feature_name}' not found for guild {guild_id}, inserting default {default}"
        )
        cur.execute(
            """
            INSERT INTO features (guild_id, feature_name, enabled)
            VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, feature_name) 
            DO UPDATE SET enabled = EXCLUDED.enabled;
        """,
            (guild_id, feature_name, default),
        )
        conn.commit()
        cur.close()
        conn.close()
        return default

    cur.close()
    conn.close()
    return result[0]


def set_feature_state(guild_id, feature_name, enabled, feature_variables=None):
    """
    Set the enabled state and optionally the feature variables (e.g., channel ID) for a feature in a guild.
    """
    cur, conn = getCur()

    cur.execute(
        """
        INSERT INTO features (guild_id, feature_name, enabled, feature_variables)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (guild_id, feature_name) 
        DO UPDATE SET enabled = EXCLUDED.enabled, feature_variables = EXCLUDED.feature_variables;
    """,
        (guild_id, feature_name, enabled, feature_variables),
    )

    conn.commit()
    cur.close()
    conn.close()


def get_feature_data(guild_id, feature_name):
    """
    Retrieve the feature data (enabled state and variables) associated with a feature in a guild.
    """
    cur, conn = getCur()

    cur.execute(
        """
        SELECT enabled, feature_variables FROM features WHERE guild_id = %s AND feature_name = %s;
    """,
        (guild_id, feature_name),
    )
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result:
        return {"enabled": result[0], "feature_variables": result[1]}
    return None


def get_guilds_with_feature_enabled(feature_name):
    """
    Return a list of guild IDs where the given feature is enabled.
    """
    cur, conn = getCur()

    cur.execute(
        """
        SELECT guild_id FROM features WHERE feature_name = %s AND enabled = TRUE;
    """,
        (feature_name,),
    )
    result = cur.fetchall()

    cur.close()
    conn.close()

    return [row[0] for row in result]


async def is_nsfw_enabled(ctx) -> bool:
    """
    Check if NSFW is enabled for the guild from the context.
    :param ctx: The context (interaction or message) to extract the guild ID.
    :return: True if enabled, otherwise False.
    """
    guild_id = ctx.guild.id  # Get guild_id from context

    if not ctx.channel.nsfw:
        await ctx.response.send_message(
            "This command only works in NSFW channels.", ephemeral=True
        )
        return False

    if is_feature_enabled(guild_id, "enable_nsfw", default=False):
        return True

    await ctx.response.send_message(
        "NSFW functions are disabled in this guild.", ephemeral=True
    )
    logging.warn(f"User {ctx.user.name} tried to use NSFW commands in a SFW guild.")

    return False
