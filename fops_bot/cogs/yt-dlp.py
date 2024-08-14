import discord
import logging
import random

from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands

from utilities.database import store_key, retrieve_key


def message_contains(message: discord.Message, _lst: list) -> bool:
    if (any(item in message.content.lower() for item in _lst)) and (
        not message.author.bot
    ):
        return True
    return False


class YTDLP(commands.Cog, name="ytdlp"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def instaListener(self, message: discord.Message):
        """
        Find messages that come from insta, download them, replace the original.
        """

        # Only care about these matches
        if not message_contains(message, ["instagram.com"]):
            return

        logging.info(f"Insta Listener processing {message}")

        """
        Fill in this section! And make it neat! We need to.

        - Extract the URL
        - Excecute yt-dlp with the URL
        - Check if it succeeded
        - Find the video or image file it produced
        - Send the image or video file back to the channel!
        """


async def setup(bot):
    await bot.add_cog(YTDLP(bot))
