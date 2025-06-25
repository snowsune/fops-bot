import discord
import logging
import random
import asyncio
import subprocess
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
from fops_bot.cogs.changelog import get_current_changelog
from fops_bot.models import get_session, KeyValueStore


class ToolCog(commands.Cog, name="ToolsCog"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.command_counter = 0  # Initialize a command counter
        self.start_time = datetime.now()  # Track when the bot started

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
        """

        statuses = [
            f"Version: {self.bot.version}",
            f"Connected to {len(self.bot.guilds)} guilds",
            f"Commands run today: {self.command_counter}",
        ]

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

    @tasks.loop(seconds=1)
    async def reset_counter_task(self):
        """
        Task to reset the command counter at midnight, using the seconds_until function.
        """
        while True:
            seconds_to_midnight = seconds_until(0, 0)
            await asyncio.sleep(seconds_to_midnight)
            self.command_counter = 0
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
        Prints the revision/version, yt-dlp version, Postgres version, GitHub hash link, and last changelog title.
        """
        dbstatus = "Unknown"
        vc = None
        yt_dlp_version = "Unknown"
        pg_version = "Unknown"
        changelog_title = "Unknown"
        github_link = "Unknown"
        fa_last_poll_str = None

        # yt-dlp version
        try:
            yt_dlp_version = (
                subprocess.check_output(["yt-dlp", "--version"]).decode().strip()
            )
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
        """
        Enable or disable NSFW commands for the entire guild.
        """
        guild_id = cast(int, interaction.guild_id)  # Cast to ensure non-None
        set_feature_state(guild_id, "enable_nsfw", state, feature_variables=None)

        status = "enabled" if state else "disabled"
        await interaction.response.send_message(
            f"NSFW functions have been {status} for this guild.", ephemeral=True
        )

    @app_commands.command(name="admin_ping")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_ping(self, ctx: discord.Interaction):
        """
        Pings the admin-configured channel.
        """
        guild_id = cast(int, ctx.guild_id)  # Cast to ensure non-None

        # Get feature data (enabled status and variables) for this guild
        feature_data = get_feature_data(guild_id, "admin_ping")

        if not feature_data or not feature_data.get("enabled"):
            await ctx.response.send_message(
                "Admin ping feature is not enabled.", ephemeral=True
            )
            return

        # Parse the feature variables (e.g., channel ID) if they exist
        admin_channel_id = feature_data.get("feature_variables")

        if not admin_channel_id:
            await ctx.response.send_message(
                "Admin channel is not configured.", ephemeral=True
            )
            return

        # Convert the raw channel ID to a Discord channel object
        channel = self.bot.get_channel(int(admin_channel_id))
        if channel:
            await channel.send(f"Ping from {ctx.user.mention}!")
            await ctx.response.send_message("Ping sent!", ephemeral=True)
        else:
            await ctx.response.send_message(
                "Admin channel not found or accessible.", ephemeral=True
            )

    @app_commands.command(name="set_admin_ping")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel to set for admin pings")
    async def set_admin_ping(
        self, ctx: discord.Interaction, channel: discord.TextChannel
    ):
        """
        Enables the admin ping feature and sets the channel.
        """
        guild_id = cast(int, ctx.guild_id)  # Cast to ensure non-None

        # Enable the admin_ping feature for this guild and set the channel
        set_feature_state(guild_id, "admin_ping", True, str(channel.id))

        await ctx.response.send_message(
            f"Admin ping feature enabled and channel set to {channel.mention}",
            ephemeral=True,
        )

    @app_commands.command(name="disable_admin_ping")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable_admin_ping(self, ctx: discord.Interaction):
        """
        Disables the admin ping feature.
        """
        guild_id = cast(int, ctx.guild_id)  # Cast to ensure non-None

        # Disable the admin_ping feature for this guild
        set_feature_state(guild_id, "admin_ping", False)

        await ctx.response.send_message("Admin ping feature disabled.", ephemeral=True)

    @app_commands.command(name="roll")
    @app_commands.describe(
        dice="The dice to roll in the format 'xdy' where x is the number of dice and y is the number of sides"
    )
    async def roll(self, ctx: discord.Interaction, dice: str):
        """
        Rolls a dice in the format 'xdy'.
        """
        try:
            num, sides = map(int, dice.lower().split("d"))
            if num <= 0 or sides <= 0:
                raise ValueError
        except ValueError:
            await ctx.response.send_message(
                "Invalid dice format. Use 'xdy' where x is the number of dice and y is the number of sides, e.g., '2d6'."
            )
            return

        rolls = [random.randint(1, sides) for _ in range(num)]
        total = sum(rolls)
        await ctx.response.send_message(f"Rolls: {rolls}\nTotal: {total}")

    @app_commands.command(name="sort_words")
    @app_commands.describe(
        message="The message whose words you want to sort by length and alphabetically."
    )
    async def sort_words(self, interaction: discord.Interaction, message: str):
        """
        Sorts all words in the provided message by length and alphabetically within each length.
        """
        # Split the message into words, remove punctuation, and convert to lowercase
        words = [word.strip(".,!?;:\"'").lower() for word in message.split()]

        # Sort words first alphabetically, then by length
        sorted_words = sorted(words, key=lambda word: (len(word), word))

        # Join the sorted words into a single string
        sorted_message = " ".join(sorted_words)

        await interaction.response.send_message(
            f"Sorted words: {sorted_message}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ToolCog(bot))
