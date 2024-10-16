import discord
import logging
import traceback

from discord import app_commands
from discord.ext import commands

from utilities.features import (
    get_feature_data,
    set_feature_state,
    get_guilds_with_feature_enabled,
)


class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_tree_error  # Manually bind the tree error here

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
        logging.warn(f"Got a tree error: {str(error)}")

        # Notify the user
        await self.notify_user(interaction, error)
        # Send error details to the admin channel
        await self.send_error_report(interaction, error)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Ignore certain errors
        if isinstance(error, commands.CommandNotFound):
            return

        # Notify the user
        await self.notify_user(ctx, error)

        # Send error details to the admin channel
        await self.send_error_report(ctx, error)

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
            logging.error(
                "Failed to send user notification for application command error"
            )

    async def send_error_report(self, interaction: discord.Interaction, error):
        """
        Send a detailed error report to the configured admin channel for app commands.
        """
        guild_id = interaction.guild.id if interaction.guild else None
        feature_data = get_feature_data(guild_id, "error_reporting")

        admin_channel_id = (
            feature_data.get("feature_variables") if feature_data else None
        )

        if admin_channel_id:
            channel = self.bot.get_channel(int(admin_channel_id))
            if channel:
                error_traceback = "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                )
                error_message = (
                    f"Error in command `{interaction.command}` triggered by {interaction.user.mention}\n"
                    f"**Error**: `{str(error)}`\n\n"
                    f"```py\n{error_traceback}\n```"
                )
                try:
                    await channel.send(error_message)
                except discord.HTTPException:
                    logging.error(
                        "Failed to send error report to admin channel for app command"
                    )
            else:
                logging.warning(f"Admin channel with ID {admin_channel_id} not found")
        else:
            logging.warning("No admin channel configured for error reporting")

    @app_commands.command(name="test_error_handler")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        state="Test function for admins to see if the error handler is catching and logging errors."
    )
    async def test_error_handler(self, interaction: discord.Interaction, state: bool):
        raise IndexError

    @app_commands.command(name="set_error_channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_error_channel(
        self, ctx: discord.Interaction, channel: discord.TextChannel
    ):
        """
        Sets the admin channel for error reporting.
        """
        guild_id = ctx.guild.id
        set_feature_state(guild_id, "error_reporting", True, str(channel.id))

        await ctx.response.send_message(
            f"Error reporting channel has been set to {channel.mention}.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(ErrorHandlerCog(bot))
