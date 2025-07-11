import re
import os
import logging
import discord

from discord import app_commands
from discord.ext import commands, tasks

from utilities.database import (
    retrieve_key_number,
    store_key_number,
    get_feature_data,
    set_feature_state,
    get_guilds_with_feature_enabled,
)


def get_current_changelog(file_path) -> (int, str):
    with open(file_path, "r") as file:
        content = file.read()

    # Regular expression to find changelog sections
    changelog_pattern = re.compile(
        r"## Changelog (\d+)(.*?)(?=## Changelog \d+|$)", re.DOTALL
    )

    changelogs = changelog_pattern.findall(content)

    if not changelogs:
        return None, None

    # Extract the latest changelog number and content
    latest_changelog = changelogs[-1]
    changelog_number = int(latest_changelog[0])
    changelog_content = latest_changelog[1].strip()

    return changelog_number, changelog_content


class Changelog(commands.Cog, name="ChangeLogCog"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        self.last_log = retrieve_key_number("LAST_CHANGELOG", 0)

        changelog_path = "/app/README.md"

        # Crack the data we need
        self.logger.info(f"Loading {changelog_path}")
        _d = get_current_changelog(changelog_path)
        cur_lognum = int(_d[0])
        cur_logstr = _d[1]

        self.logger.info(f"Changelog is currently {cur_lognum}/{self.last_log}.")
        self.logger.debug(f"Changelog content was: {cur_logstr}")

        if cur_lognum == self.last_log:
            # If they match, we're done and we can pack up
            self.logger.info("No new changelog to report.")
            return

        # Now we need to notify all guilds that have changelog notifications enabled
        guilds_with_changelog_enabled = get_guilds_with_feature_enabled(
            "changelog_alert"
        )

        for guild_id in guilds_with_changelog_enabled:
            feature_data = get_feature_data(guild_id, "changelog_alert")
            if not feature_data or not feature_data.get("enabled"):
                continue

            # Get the channel ID for the changelog alert
            channel_id = feature_data.get("feature_variables")
            if not channel_id:
                self.logger.warning(
                    f"No channel set for changelog alerts in guild {guild_id}"
                )
                continue

            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                self.logger.warning(
                    f"Could not find channel {channel_id} in guild {guild_id}"
                )
                continue

            # Replace any placeholders in the changelog text
            cur_logstr_formatted = f"# Changelog {cur_lognum}\n" + cur_logstr.replace(
                "{{version}}", self.bot.version
            )

            # Post the changelog
            try:
                await channel.send(cur_logstr_formatted)
            except discord.errors.Forbidden as e:
                self.logger.warning(
                    f"When posting changelog got forbidden/lost ch. {e}. Removing from db."
                )
                set_feature_state(guild_id, "changelog_alert", False)

        # Update the db after posting
        store_key_number("LAST_CHANGELOG", cur_lognum)

        self.logger.info("Changelog done!")

    @app_commands.command(name="set_changelog_alert_channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel to set for changelog alerts")
    async def set_changelog_alert_channel(
        self, ctx: discord.Interaction, channel: discord.TextChannel
    ):
        """
        Set the channel to receive changelog alerts for the guild.
        """
        guild_id = ctx.guild_id

        # Enable the changelog_alert feature for this guild and set the channel
        set_feature_state(guild_id, "changelog_alert", True, str(channel.id))

        await ctx.response.send_message(
            f"Changelog alerts have been set for {channel.mention}.", ephemeral=True
        )

    @app_commands.command(name="disable_changelog_alert_channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable_changelog_alert_channel(self, ctx: discord.Interaction):
        """
        Disable changelog alerts for the guild.
        """
        guild_id = ctx.guild_id

        # Disable the changelog_alert feature for this guild
        set_feature_state(guild_id, "changelog_alert", False)

        await ctx.response.send_message(
            "Changelog alerts have been disabled.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Changelog(bot))
