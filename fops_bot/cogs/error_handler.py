import discord
import logging
import traceback
import os
from discord import app_commands
from discord.ext import commands

from cogs.guild_cog import get_guild
from utilities.guild_log import (
    info as guild_log_info,
    warning as guild_log_warning,
    error as guild_log_error,
)


class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_tree_error  # Manually bind the tree error here
        self.logger = logging.getLogger(__name__)

        # If debug mode is enabled.
        self.debug = str(os.environ.get("DEBUG", "0")).lower() in (
            "true",
            "1",
            "t",
            "yes",
        )

    async def cog_load(self):
        if not self.debug:
            # Remove test command from tree when loaded
            self.__cog_app_commands__.remove(self.test_error_handler)

    @commands.Cog.listener()
    async def on_ready(self):
        # Sync the commands this cog provides
        await self.bot.tree.sync()

    async def on_tree_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """
        Global handler for all app command errors (slash commands).
        """
        guild_id = getattr(interaction.guild, "id", None)
        guild_log_warning(self.logger, guild_id, f"Got a tree error: {str(error)}")

        # Notify the user
        await self.notify_user(interaction, error)
        # Send error details to the admin channel
        await self.send_error_report(interaction, error)

        # Re-raise to allow upstream handlers/loggers to process the exception
        raise error

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Ignore certain errors
        if isinstance(error, commands.CommandNotFound):
            return

        # Notify the user
        await self.notify_user(ctx, error)

        # Send error details to the admin channel
        await self.send_error_report(ctx, error)

        # Re-raise to allow upstream handlers/loggers to process the exception
        raise error

    async def notify_user(self, interaction: discord.Interaction, error):
        """
        Notify the user who triggered the application command error.
        """
        try:
            await interaction.response.send_message(
                "Oops! Something went wrong. An admin has been notified.",
                ephemeral=True,
            )
        except discord.HTTPException:
            guild_log_error(
                self.logger,
                getattr(interaction.guild, "id", None),
                "Failed to send user notification for application command error",
            )

    async def send_error_report(self, interaction: discord.Interaction, error):
        """
        Send a detailed error report to the guild's admin channel.

        Uses the admin_channel_id from the guild settings.
        """
        if not interaction.guild:
            self.logger.debug("No guild for interaction, skipping error report")
            return

        # Get guild settings
        guild_settings = get_guild(interaction.guild.id)
        if not guild_settings:
            guild_log_warning(
                self.logger,
                interaction.guild.id,
                f"No guild settings found for {interaction.guild.id}",
            )
            return

        admin_channel_id = guild_settings.admin_channel()
        if not admin_channel_id:
            guild_log_info(
                self.logger,
                interaction.guild.id,
                "No admin channel configured for guild",
            )
            return

        channel = self.bot.get_channel(admin_channel_id)
        if not channel:
            guild_log_warning(
                self.logger,
                interaction.guild.id,
                f"Admin channel {admin_channel_id} not found",
            )
            return

        # Format and send error report
        error_traceback = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        error_message = (
            f"⚠️ **Error in command** `{interaction.command}`\n"
            f"**User**: {interaction.user.mention}\n"
            f"**Error**: `{str(error)}`\n\n"
            f"```py\n{error_traceback}\n```"
        )
        try:
            await channel.send(error_message)
        except discord.HTTPException as e:
            guild_log_error(
                self.logger,
                interaction.guild.id,
                f"Failed to send error report to admin channel: {e}",
            )

    @app_commands.command(name="test_error_handler")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        state="Test function for admins to see if the error handler is catching and logging errors."
    )
    async def test_error_handler(self, interaction: discord.Interaction, state: bool):
        """Test the error handler by raising an intentional error."""
        raise IndexError("This is a test error to verify the error handler works!")


async def setup(bot):
    await bot.add_cog(ErrorHandlerCog(bot))
