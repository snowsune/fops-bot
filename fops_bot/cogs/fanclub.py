# 2023, Fops Bot
# MIT License

import discord
import logging
import asyncio
import time
import random
import pytz
import os
import python_weather
import yaml
import shutil

from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone

from utilities.common import seconds_until
from utilities.database import retrieve_key, store_key


class FanclubCog(commands.Cog, name="FanclubCog"):
    def __init__(self, bot):
        self.bot = bot
        self.localtz = pytz.timezone("US/Eastern")

    def getStat(self, guild: int, addOne=False):
        """
        Tell me how many times a guild has been booped
        """

        bc_key = f"boopCount_{guild}"

        bc = int(retrieve_key(bc_key, 0))

        if addOne:
            store_key(bc_key, bc + 1)
            bc = retrieve_key(bc_key)

        return bc

    @commands.Cog.listener("on_message")
    async def boopListener(self, message: discord.Message):
        logging.debug(f"Boop Listener processing {message}")

        # Check for boops!
        boops = ["boop", "boops", "boop'd"]
        if (any(item in message.content.lower() for item in boops)) and (
            not message.author.bot
        ):
            logging.debug(f"Boop detected in {message}, guild was {message.guild}")
            await message.reply(f"{self.getStat(message.guild.id, True)} boops!")


async def setup(bot):
    await bot.add_cog(FanclubCog(bot))
