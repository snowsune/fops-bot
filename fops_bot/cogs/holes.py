import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from fops_bot.models import get_session, Hole


class HolesCog(commands.Cog, name="HolesCog"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="configure_hole",
        description="Configure a hole to forward messages from this channel to another channel or user.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        channel="The channel to install the hole in",
        forwarded_id="The channel ID or user ID to forward messages to",
        is_pm="Whether to forward to a user (PM)",
        anonymize="Whether to anonymize the forwarded messages",
    )
    async def configure_hole(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        forwarded_id: str,
        is_pm: bool = False,
        anonymize: bool = False,
    ):
        """
        Configure a hole: messages from the specified channel will be forwarded to another channel or user.
        """
        # Only allow admins
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You must be an administrator to use this command.", ephemeral=True
            )
            return

        # Validate forwarded_id
        try:
            forwarded_id_int = int(forwarded_id)
        except ValueError:
            await interaction.response.send_message(
                "The forwarded_id must be a valid Discord channel or user ID.",
                ephemeral=True,
            )
            return

        # Store in DB
        with get_session() as session:
            # Check if a hole already exists for this channel
            existing = (
                session.query(Hole)
                .filter_by(channel_id=channel.id, guild_id=channel.guild.id)
                .first()
            )
            if existing:
                existing.forwarded_channel_id = forwarded_id_int
                existing.is_pm = is_pm
                existing.anonymize = anonymize
                session.commit()
                await interaction.response.send_message(
                    f"Updated hole for <#{channel.id}>.", ephemeral=True
                )
            else:
                new_hole = Hole(
                    guild_id=channel.guild.id,
                    channel_id=channel.id,
                    forwarded_channel_id=forwarded_id_int,
                    is_pm=is_pm,
                    anonymize=anonymize,
                )
                session.add(new_hole)
                session.commit()
                await interaction.response.send_message(
                    f"Configured new hole for <#{channel.id}>.", ephemeral=True
                )


async def setup(bot):
    await bot.add_cog(HolesCog(bot))
