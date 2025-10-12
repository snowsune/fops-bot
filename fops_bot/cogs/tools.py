import discord
import logging
import random
import asyncio
import subprocess
import re
import os
import aiohttp
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
from typing import Optional, cast

from utilities.common import seconds_until
from utilities.database import (
    store_key,
    retrieve_key,
    is_feature_enabled,
    set_feature_state,
    get_feature_data,
    get_guilds_with_feature_enabled,
    store_key_number,
    retrieve_key_number,
    get_db_info,
)
from cogs.changelog import get_current_changelog
from fops_bot.models import get_session, KeyValueStore

YTDLP_API_URL = os.environ.get("YTDLP_API_URL", "http://yt-dlp:5000")


class ToolCog(commands.Cog, name="ToolsCog"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.command_counter = 0  # Initialize a command counter
        self.start_time = datetime.now()  # Track when the bot started
        self.bot.usage_today = self.command_counter

    @commands.Cog.listener()
    async def on_ready(self):
        # Start tasks
        self.update_status.start()
        self.reset_counter_task.start()

    @tasks.loop(minutes=1)  # Run every minute
    async def update_status(self):
        """
        Background task that updates the bot's status every minute, cycling between:
        - The bot's version
        - The number of guilds connected
        - The number of commands run today
        - Processing downloads (if active jobs)
        """

        statuses = [
            f"Version: {self.bot.version}",
            f"Connected to {len(self.bot.guilds)} guilds",
            f"Commands run today: {self.command_counter}",
        ]

        # Check for active yt-dlp jobs
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{YTDLP_API_URL}/health", timeout=3) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        jobs_count = data.get("jobs", 0)
                        if jobs_count > 0:
                            statuses.append(
                                f"Processing {jobs_count} download{'s' if jobs_count > 1 else ''}"
                            )
        except Exception:
            self.logger.error("Failed to check yt-dlp jobs!")

        # Cycle through the statuses randomly
        new_status = random.choice(statuses)

        # Set the bot's activity status
        await self.bot.change_presence(activity=discord.Game(name=new_status))

    @commands.Cog.listener()
    async def on_app_command_completion(self, ctx, cmd):
        """
        Increment the command counter every time a command is run.
        """
        self.command_counter += 1
        self.bot.usage_today = self.command_counter

    @tasks.loop(seconds=1)
    async def reset_counter_task(self):
        """
        Task to reset the command counter at midnight, using the seconds_until function.
        """
        while True:
            seconds_to_midnight = seconds_until(0, 0)
            await asyncio.sleep(seconds_to_midnight)
            self.command_counter = 0
            self.bot.usage_today = self.command_counter
            self.logger.info("Command counter reset at midnight.")

    @app_commands.command(name="invite_bot")
    async def invite_bot(self, ctx: discord.Interaction):
        await ctx.response.send_message(
            f"Use this link to invite me to your server!\nhttps://discord.com/oauth2/authorize?client_id=983461462896963744",
            ephemeral=True,
        )

    @app_commands.command(name="version")
    async def version(self, ctx: discord.Interaction):
        """
        Show the bot's version, health and other information!
        """
        dbstatus = "Unknown"
        vc = None
        yt_dlp_version = "Unknown"
        pg_version = "Unknown"
        changelog_title = "Unknown"
        github_link = "Unknown"
        fa_last_poll_str = None

        # yt-dlp version from service health endpoint
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{YTDLP_API_URL}/health", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        yt_dlp_version = data.get("yt-dlp_version", "Unknown")
                        # Also grab job count for bonus info
                        jobs_count = data.get("jobs", 0)
                        if jobs_count > 0:
                            yt_dlp_version += f" ({jobs_count} jobs)"
                    else:
                        yt_dlp_version = f"Service unavailable (HTTP {resp.status})"
        except asyncio.TimeoutError:
            yt_dlp_version = "Timeout (service not responding)"
        except Exception as e:
            yt_dlp_version = f"Error: {e}"

        # Postgres version
        try:
            pg_version = get_db_info()
        except Exception as e:
            pg_version = f"Error: {e}"

        # GitHub hash link (extract short hash from version string)
        short_hash = None
        if self.bot.version and self.bot.version != "None":
            # Try to extract the git hash (after last '-g' or last 8 chars if present)
            if "-g" in self.bot.version:
                short_hash = self.bot.version.split("-g")[-1].split("-")[0]
            else:
                short_hash = self.bot.version[-8:]
            github_link = f"https://github.com/Snowsune/fops-bot/commit/{short_hash}"
        else:
            github_link = "Not available"

        # Last changelog title/content
        try:
            changelog_path = "/app/README.md"
            changelog_num, changelog_content = get_current_changelog(changelog_path)
            if changelog_num is not None and changelog_content:
                changelog_title = (
                    f"Changelog {changelog_num}: {changelog_content.splitlines()[0]}"
                )
            elif changelog_num is not None:
                changelog_title = f"Changelog {changelog_num}: (no content)"
            else:
                changelog_title = "Not found"
        except Exception as e:
            changelog_title = f"Error: {e}"

        # DB status and version count (sanitize vc)
        try:
            if True:
                try:
                    vc = retrieve_key_number("version_count", 0)
                    if not isinstance(vc, int) or vc is None:
                        vc = 0
                    self.logger.info(f"Retrieved vc as {vc}")
                    dbstatus = "Ready"
                except Exception as e:
                    self.logger.error(f"Error retrieving key, error was {e}")
                    dbstatus = "Not Ready (connected but cant retrieve now)"

                store_key_number("version_count", (vc or 0) + 1)
            else:
                dbstatus = "Not Ready"
        except Exception as e:
            self.logger.error(f"Couldn't check db at all, error was {e}")

        with get_session() as session:
            kv = session.get(KeyValueStore, "fa_last_poll")
            if kv and kv.value:
                fa_last_poll_str = f"Last FA Poll was <t:{kv.value}:R>."

        msg = (
            f"**Version:** `{self.bot.version}`\n"
            f"**GitHub:** {github_link}\n"
            f"**yt-dlp version:** `{yt_dlp_version}`\n"
            f"**Postgres version:** `{pg_version}`\n"
            f"**DB status:** `{dbstatus}` (access `{vc}`)\n"
            f"**Last changelog:** {changelog_title}"
        )
        if fa_last_poll_str:
            msg += f"\n{fa_last_poll_str}"
        await ctx.response.send_message(msg)

    @app_commands.command(name="enable_nsfw")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(state="Enable or disable NSFW commands for the guild")
    async def enable_nsfw(self, interaction: discord.Interaction, state: bool):
        guild_id = cast(int, interaction.guild_id)  # Cast to ensure non-None
        set_feature_state(guild_id, "enable_nsfw", state, feature_variables=None)

        status = "enabled" if state else "disabled"
        await interaction.response.send_message(
            f"NSFW functions have been {status} for this guild.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ToolCog(bot))
