from __future__ import annotations

import logging
from typing import Callable

from fops_bot.models import Guild, get_session

"""
Dunno where else to put this lol~
hooks python's logging system to use my little custom guild_log bit!
"""


def _with_guild(guild_id: int | None, fn: Callable[[Guild], None]) -> None:
    if guild_id is None:
        return
    with get_session() as session:
        guild = session.get(Guild, guild_id)
        if not guild:
            return
        fn(guild)
        session.commit()


def _log(
    logger: logging.Logger, level: str, guild_id: int | None, message: str
) -> None:
    getattr(logger, level)(message)

    def updater(guild: Guild) -> None:
        guild.append_log_entry(level.upper(), message)

    _with_guild(guild_id, updater)


def info(logger: logging.Logger, guild_id: int | None, message: str) -> None:
    _log(logger, "info", guild_id, message)


def warning(logger: logging.Logger, guild_id: int | None, message: str) -> None:
    _log(logger, "warning", guild_id, message)


def error(logger: logging.Logger, guild_id: int | None, message: str) -> None:
    _log(logger, "error", guild_id, message)
