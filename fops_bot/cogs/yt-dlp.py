import discord
import logging
import random
import subprocess
import os

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

        canonical_url = "instagram.com"

        # Only care about these matches
        if not message_contains(message, [canonical_url, "instagramez.com"]):
            return

        logging.info(f"Insta Listener processing {message}")

        # Extract the URL
        url = None
        for word in message.content.split():
            if canonical_url in word:
                url = word
                break

        if not url:
            logging.warn(
                f'Found {canonical_url} in message "{message}"but could not extract url'
            )
            return  # No valid URL found

        # Define output directory
        output_dir = "/tmp/ytdlp_output"
        os.makedirs(output_dir, exist_ok=True)

        # Execute yt-dlp with the URL
        try:
            command = [
                "yt-dlp",
                url,
                "-o",
                os.path.join(output_dir, "%(title)s.%(ext)s"),
            ]
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"yt-dlp failed: {e}")
            return

        # Find the video or image file it produced
        files = os.listdir(output_dir)
        if not files:
            logging.error("No files found in output directory")
            return

        # Assume the first file is the desired one (could add logic to choose based on extension)
        file_path = os.path.join(output_dir, files[0])

        # Send the image or video file back to the channel
        if os.path.isfile(file_path):
            await message.channel.send(file=discord.File(file_path))
            # Clean up
            os.remove(file_path)

        # Remove the output directory
        os.rmdir(output_dir)

    @commands.Cog.listener("on_message")
    async def facebookListener(self, message: discord.Message):
        """
        Same as insta, but for facebook.
        """

        canonical_url = "facebook.com"

        # Only care about these matches
        if not message_contains(message, [canonical_url]):
            return

        logging.info(f"Facebook Listener processing {message}")

        # Extract the URL
        url = None
        for word in message.content.split():
            if canonical_url in word:
                url = word
                break

        if not url:
            logging.warn(
                f'Found {canonical_url} in message "{message}"but could not extract url'
            )
            return  # No valid URL found

        # Define output directory
        output_dir = "/tmp/ytdlp_output"
        os.makedirs(output_dir, exist_ok=True)

        # Execute yt-dlp with the URL
        try:
            command = [
                "yt-dlp",
                url,
                "-o",
                os.path.join(output_dir, "%(title)s.%(ext)s"),
            ]
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"yt-dlp failed: {e}")
            return

        # Find the video or image file it produced
        files = os.listdir(output_dir)
        if not files:
            logging.error("No files found in output directory")
            return

        # Assume the first file is the desired one (could add logic to choose based on extension)
        file_path = os.path.join(output_dir, files[0])

        # Send the image or video file back to the channel
        if os.path.isfile(file_path):
            await message.channel.send(file=discord.File(file_path))
            # Clean up
            os.remove(file_path)

        # Remove the output directory
        os.rmdir(output_dir)

    @commands.Cog.listener("on_message")
    async def twitterListener(self, message: discord.Message):
        """
        Twitter/x
        """

        canonical_url = "x.com"

        # Only care about these matches
        if not message_contains(
            message, [canonical_url, "fixupx.com", "fxtwitter.com"]
        ):
            return

        logging.info(f"Twitter Listener processing {message}")

        # Extract the URL
        url = None
        for word in message.content.split():
            if canonical_url in word:
                url = word
                break

        if not url:
            logging.warn(
                f'Found {canonical_url} in message "{message}"but could not extract url'
            )
            return  # No valid URL found

        # Define output directory
        output_dir = "/tmp/ytdlp_output"
        os.makedirs(output_dir, exist_ok=True)

        # Execute yt-dlp with the URL
        try:
            command = [
                "yt-dlp",
                url,
                "-o",
                os.path.join(output_dir, "%(title)s.%(ext)s"),
            ]
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"yt-dlp failed: {e}")
            return

        # Find the video or image file it produced
        files = os.listdir(output_dir)
        if not files:
            logging.error("No files found in output directory")
            return

        # Assume the first file is the desired one (could add logic to choose based on extension)
        file_path = os.path.join(output_dir, files[0])

        # Send the image or video file back to the channel
        if os.path.isfile(file_path):
            await message.channel.send(file=discord.File(file_path))
            # Clean up
            os.remove(file_path)

        # Remove the output directory
        os.rmdir(output_dir)


async def setup(bot):
    await bot.add_cog(YTDLP(bot))
