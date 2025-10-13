"""
Guild settings and configuration cog

Guild settings are managed externally via https://snowsune.net/fops
This cog handles guild tracking and synchronization with the database.
"""

import os
import discord
import logging
from discord.ext import commands
from fops_bot.models import get_session, Guild


logger = logging.getLogger(__name__)
OWNER_UID = int(os.getenv("OWNER_UID", "0"))


def get_guild(ctx_or_guild_id) -> Guild | None:
    """
    Returns a guild DB object (with settings!)

    Args:
        ctx_or_guild_id: Either a guild_id (int) or a context object with .guild.id

    Example:
        from cogs.guild_cog import get_guild

        # With context
        guild = get_guild(interaction)
        if guild and guild.nsfw():
            # NSFW allowed
            pass

        # With guild_id
        guild = get_guild(interaction.guild.id)

        if guild and guild.is_channel_ignored(interaction):
            # Channel is ignored
            return
    """

    # Extract guild_id from context or use the id directly
    if isinstance(ctx_or_guild_id, int):
        guild_id = ctx_or_guild_id
    elif hasattr(ctx_or_guild_id, "guild") and ctx_or_guild_id.guild:
        guild_id = ctx_or_guild_id.guild.id
    else:
        logger.warning(f"Invalid input to get_guild: {type(ctx_or_guild_id)}")
        return None

    with get_session() as session:
        return session.get(Guild, guild_id)


def ensure_guild_exists(guild_id: int, guild_name: str = "") -> Guild:
    """
    Ensure a guild exists in the database, create if it doesn't.
    """
    with get_session() as session:
        guild = session.get(Guild, guild_id)
        if not guild:
            logger.warning(
                f"Guild {guild_id} ({guild_name}) not found in database, creating..."
            )
            guild = Guild(
                guild_id=guild_id,
                name=guild_name,
                frozen=False,
                allow_nsfw=False,
                enable_dlp=True,
                twitter_obfuscate=False,
                admin_channel_id=None,
                ignored_channels=[],
            )
            session.add(guild)
            session.commit()
            session.refresh(guild)
            logger.info(f"Guild {guild_id} ({guild_name}) created in database.")
        return guild


def update_guild_name(guild_id: int, guild_name: str) -> None:
    """Update guild name in the database."""
    with get_session() as session:
        guild = session.get(Guild, guild_id)
        if guild and guild.name != guild_name:
            guild.name = guild_name
            session.commit()
            logger.info(f"Updated guild name for {guild_id} to {guild_name}")


class GuildSettingsCog(commands.Cog):
    """Manages guild tracking and synchronization."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        """Sync all current guilds to the database on startup."""
        self.logger.info("Syncing guilds to database...")
        synced_count = 0
        for guild in self.bot.guilds:
            ensure_guild_exists(guild.id, guild.name)
            synced_count += 1
        self.logger.info(f"Synced {synced_count} guilds to database.")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """When the bot joins a guild, ensure it's in the database."""
        self.logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
        ensure_guild_exists(guild.id, guild.name)

        # Send welcome DM to the guild owner
        if guild.owner:
            try:
                welcome_message = (
                    f"**TY for adding my bot to {guild.name}!**\n\n"
                    f"Fops Bot is now active in your server! You can manage all settings, "
                    f"subscriptions, and features through my web dashboard:\n\n"
                    f"**[snowsune.net/fops](https://snowsune.net/fops/redirect/)**\n\n"
                    f"If you need help, tips or have feedback! Contact vixi@snowsune.net or PM me on discord!\n\n"
                    f"*This message was sent because you own a server where Fops Bot was just added~*"
                )
                await guild.owner.send(welcome_message)
                self.logger.info(
                    f"Sent welcome DM to {guild.owner.name} for {guild.name}"
                )
            except discord.errors.Forbidden:
                self.logger.warning(f"Could not DM {guild.owner.name} - DMs disabled")
            except Exception as e:
                self.logger.error(f"Error sending welcome DM: {e}")

        # Hehe >:3 Notify ME about the new guild! Im nosey :P
        if OWNER_UID:
            try:
                owner_user = await self.bot.fetch_user(OWNER_UID)
                owner_notification = (
                    f"**Bot joined a new guild!**\n\n"
                    f"**Guild:** {guild.name}\n"
                    f"**Guild ID:** {guild.id}\n"
                    f"**Owner:** {guild.owner.name if guild.owner else 'Unknown'}\n"
                    f"**Members:** {guild.member_count}\n"
                    f"**Created:** <t:{int(guild.created_at.timestamp())}:R>"
                )
                await owner_user.send(owner_notification)
                self.logger.info(f"Notified vixi about new guild: {guild.name}")
            except Exception as e:
                self.logger.error(f"Error notifying viix: {e}")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Log when the bot leaves a guild (but keep the data)."""
        self.logger.info(f"Left guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Update guild name when it changes."""
        if before.name != after.name:
            update_guild_name(after.id, after.name)


async def setup(bot):
    """Load the cog."""
    await bot.add_cog(GuildSettingsCog(bot))
