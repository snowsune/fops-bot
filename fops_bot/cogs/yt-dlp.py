import discord
import logging
import random
import subprocess
import os

from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands

from utilities.database import store_key, retrieve_key


class VideoExtractor:
    def __init__(self, _message):
        self.message = _message

        # Defines
        self.output_dir = "/tmp/ytdlp_output"

    def __enter__(self) -> str:
        logging.info(f"Video Extractor Processing {self.message}")

        # Extract the URL
        url = None
        for word in self.message.split():
            if "://" in word:
                url = word
                break

        if not url:
            logging.warn(
                f'Found link in message "{self.message}"but could not extract url'
            )
            return None  # No valid URL found

        # Define output directory
        os.makedirs(self.output_dir, exist_ok=True)

        # Execute yt-dlp with the URL
        try:
            command = [
                "yt-dlp",
                url,
                "-o",
                os.path.join(self.output_dir, "%(title)s.%(ext)s"),
            ]
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"yt-dlp failed: {e}")
            return

        # Find the video or image file it produced
        files = os.listdir(self.output_dir)
        if not files:
            logging.error("No files found in output directory")
            return

        # Assume the first file is the desired one (could add logic to choose based on extension)
        self.file_path = os.path.join(self.output_dir, files[0])

        # If we succeed, return the file path
        if os.path.isfile(self.file_path):
            return self.file_path
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.isfile(self.file_path):
            # Clean up
            os.remove(self.file_path)

        # Remove the output directory
        os.rmdir(self.output_dir)


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

        valid_urls = ["instagram.com", "instagramez.com"]

        # Only care about these matches
        if not message_contains(message, valid_urls):
            return

        logging.info(f'Insta Listener caught message "{message.content}"')

        with VideoExtractor(message.content) as video:
            if video is not None:
                await message.channel.send(file=discord.File(video))

    @commands.Cog.listener("on_message")
    async def facebookListener(self, message: discord.Message):
        """
        Same as insta, but for facebook.
        """

        valid_urls = ["facebook.com"]

        # Only care about these matches
        if not message_contains(message, valid_urls):
            return

        logging.info(f'Facebook Listener caught message "{message.content}"')

        with VideoExtractor(message.content) as video:
            if video is not None:
                await message.channel.send(file=discord.File(video))

    @commands.Cog.listener("on_message")
    async def twitterListener(self, message: discord.Message):
        """
        Twitter/x
        """

        valid_urls = ["x.com", "fixupx.com", "fxtwitter.com"]

        # Only care about these matches
        if not message_contains(message, valid_urls):
            return

        logging.info(f'Twitter Listener caught message "{message.content}"')

        with VideoExtractor(message.content) as video:
            if video is not None:
                await message.channel.send(file=discord.File(video))


async def setup(bot):
    await bot.add_cog(YTDLP(bot))
