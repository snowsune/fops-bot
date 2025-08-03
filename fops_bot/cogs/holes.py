import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from fops_bot.models import get_session, Hole, HoleUserColor
import random

COLOR_CHOICES = [
    "Blue",
    "Dark Blue",
    "Navy",
    "Teal",
    "Aqua",
    "Cyan",
    "Green",
    "Red",
    "Yellow",
    "Purple",
    "Orange",
    "Pink",
    "Teal",
    "Lime",
    "Magenta",
    "Brown",
    "Gray",
    "Black",
    "White",
    "Azure",
    "Violet",
    "Indigo",
    "Turquoise",
    "Coral",
    "Maroon",
    "Olive",
    "Teal",
    "Aqua",
    "Cyan",
    "Green",
    "Red",
    "Yellow",
    "Sunflower",
    "Emerald",
    "Jade",
    "Cobalt",
    "Plum",
    "Lavender",
    "Mint",
]


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
                existing.forwarded_channel_id = forwarded_id_int  # type: ignore
                existing.is_pm = bool(is_pm)  # type: ignore
                existing.anonymize = bool(anonymize)  # type: ignore
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

    def get_name(self, anonymized: bool, user, guild_id, session):
        if not anonymized:
            # Easy case: just return the display name
            return user.display_name

        # Anonymized: assign or get color
        color_entry = (
            session.query(HoleUserColor)
            .filter_by(guild_id=guild_id, user_id=user.id)
            .first()
        )
        if not color_entry:
            used_colors = set(
                row.color
                for row in session.query(HoleUserColor)
                .filter_by(guild_id=guild_id)
                .all()
            )
            available_colors = [c for c in COLOR_CHOICES if c not in used_colors]
            if not available_colors:
                color = random.choice(COLOR_CHOICES)
            else:
                color = random.choice(available_colors)
            color_entry = HoleUserColor(guild_id=guild_id, user_id=user.id, color=color)
            session.add(color_entry)
            session.commit()
        return color_entry.color

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
                    # This isn't a hole guild/channel pairing
                    return

                # Don't forward messages starting with '('
                if bool(hole.anonymize) and message.content.strip().startswith("("):
                    return

                bot = self.bot
                sent = False

                # Use get_name for display
                display = self.get_name(
                    bool(hole.anonymize), message.author, message.guild.id, session
                )
                content = message.content
                if bool(hole.anonymize):
                    forward_text = f"{display}\n>>> {content}"
                else:
                    forward_text = f"{display}: {content}"
                if bool(hole.is_pm):
                    user = bot.get_user(
                        hole.forwarded_channel_id
                    ) or await bot.fetch_user(hole.forwarded_channel_id)
                    if user:
                        await user.send(forward_text)
                        sent = True
                else:
                    channel = bot.get_channel(
                        hole.forwarded_channel_id
                    ) or await bot.fetch_channel(hole.forwarded_channel_id)
                    if channel:
                        await channel.send(forward_text)
                        sent = True
                if sent:
                    try:
                        await message.add_reaction("\U0001f4e7")  # 📧
                    except Exception:
                        pass

        # --- DM TO HOLE CHANNEL ---
        elif isinstance(message.channel, discord.DMChannel):
            if message.content.strip().startswith(
                "("
            ) or message.content.strip().startswith("/"):
                return
            with get_session() as session:
                hole = (
                    session.query(Hole)
                    .filter_by(forwarded_channel_id=message.author.id, is_pm=True)
                    .first()
                )
                if not hole:
                    return
                bot = self.bot
                channel = bot.get_channel(hole.channel_id) or await bot.fetch_channel(
                    hole.channel_id
                )
                sent = False
                if channel:
                    await channel.send(
                        f"{message.author.display_name}\n>>> {message.content}"
                    )
                    sent = True
                if sent:
                    try:
                        await message.add_reaction("\U0001f4e7")  # 📧
                    except Exception:
                        pass


async def setup(bot):
    await bot.add_cog(HolesCog(bot))
