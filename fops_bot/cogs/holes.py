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
        # Only allow admins (check only if user is a Member)
        from discord import Member

        if isinstance(interaction.user, Member):
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
                existing.is_pm = bool(is_pm)
                existing.anonymize = bool(anonymize)
                session.commit()
                await interaction.response.send_message(
                    f"Updated hole for <#{channel.id}>.", ephemeral=True
                )
            else:
                new_hole = Hole(
                    guild_id=channel.guild.id,
                    channel_id=channel.id,
                    forwarded_channel_id=forwarded_id_int,
                    is_pm=bool(is_pm),
                    anonymize=bool(anonymize),
                )
                session.add(new_hole)
                session.commit()
                await interaction.response.send_message(
                    f"Configured new hole for <#{channel.id}>.", ephemeral=True
                )

    @app_commands.command(
        name="remove_hole", description="Remove a hole forwarding from a channel."
    )
    @app_commands.describe(channel="The channel to remove the hole from")
    async def remove_hole(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        # Only allow admins (check only if user is a Member)
        from discord import Member

        if isinstance(interaction.user, Member):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "You must be an administrator to use this command.", ephemeral=True
                )
                return

        # Remove from DB
        with get_session() as session:
            hole = (
                session.query(Hole)
                .filter_by(channel_id=channel.id, guild_id=channel.guild.id)
                .first()
            )
            if hole:
                session.delete(hole)
                session.commit()
                await interaction.response.send_message(
                    f"Removed hole for <#{channel.id}>.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"No hole found for <#{channel.id}>.", ephemeral=True
                )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return

        # --- GUILD TO HOLE RECIPIENT ---
        if message.guild:
            with get_session() as session:
                hole = (
                    session.query(Hole)
                    .filter_by(channel_id=message.channel.id, guild_id=message.guild.id)
                    .first()
                )
                if not hole:
                    return

                # Use bool(hole.anonymize) to check value
                if bool(hole.anonymize) and message.content.strip().startswith("("):
                    return

                # Prepare content
                content = message.content
                if bool(hole.anonymize):
                    # Remove username, just send the message
                    content = content
                else:
                    # Include username
                    content = f"{message.author.display_name}: {content}"
                # Forward to channel or user
                bot = self.bot
                if bool(hole.is_pm):
                    # Forward to user
                    user = bot.get_user(
                        hole.forwarded_channel_id
                    ) or await bot.fetch_user(hole.forwarded_channel_id)
                    if user:
                        await user.send(content)
                else:
                    # Forward to channel
                    channel = bot.get_channel(
                        hole.forwarded_channel_id
                    ) or await bot.fetch_channel(hole.forwarded_channel_id)
                    if channel:
                        await channel.send(content)

        # --- DM TO HOLE CHANNEL ---
        elif isinstance(message.channel, discord.DMChannel):
            # Don't forward commands or messages starting with '('
            if message.content.strip().startswith(
                "("
            ) or message.content.strip().startswith("/"):
                return
            with get_session() as session:
                # Find a hole where this user is the recipient (is_pm=True)
                hole = (
                    session.query(Hole)
                    .filter_by(forwarded_channel_id=message.author.id, is_pm=True)
                    .first()
                )
                if not hole:
                    return
                # Forward to the configured channel, keeping their display name
                bot = self.bot
                channel = bot.get_channel(hole.channel_id) or await bot.fetch_channel(
                    hole.channel_id
                )
                if channel:
                    await channel.send(
                        f"{message.author.display_name}\n>>> {message.content}"
                    )


async def setup(bot):
    await bot.add_cog(HolesCog(bot))
