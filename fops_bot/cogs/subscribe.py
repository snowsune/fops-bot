import os
import faapi  # type: ignore
import discord
import logging
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from requests.cookies import RequestsCookieJar
from datetime import datetime, timezone
from fops_bot.models import get_session, Subscription
from .subscribe_resources.ui import (
    AddSubscriptionModal,
    ServiceDropdown,
    ChannelSelectDropdown,
    RemoveDropdown,
    ManageFollowingView,
)

# Load FurAffinity cookies from environment variables
FA_COOKIE_A = os.getenv("FA_COOKIE_A")
FA_COOKIE_B = os.getenv("FA_COOKIE_B")


def get_all_in_guild(guild_id: int) -> List[Subscription]:
    """Return all Subscription entries for a given guild."""
    with get_session() as session:
        return list(session.query(Subscription).filter_by(guild_id=guild_id).all())


class SubscribeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.fa_cookie_a = str(FA_COOKIE_A)
        self.fa_cookie_b = str(FA_COOKIE_B)

        if len(self.fa_cookie_a) < 10 or len(self.fa_cookie_b) < 10:
            self.logger.warning("FA cookies look short/invalid.")

    @app_commands.command(
        name="manage_following",
        description="Manage your followed FA/E6 feeds in this guild.",
    )
    async def manage_following(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.DMChannel):
            # Allow personal message setup in DMs
            desc = "Configure personal message subscriptions."
            embed = discord.Embed(
                title="Manage Personal Following",
                description=desc,
                color=discord.Color.blue(),
            )

            # Only show subscriptions for this user in DMs
            with get_session() as session:
                subs = (
                    session.query(Subscription)
                    .filter_by(user_id=interaction.user.id, is_pm=True)
                    .all()
                )
            if subs:
                sub_lines = [
                    f"- `{sub.service_type}`: `{sub.search_criteria}` with filters `{sub.filters}`"
                    for sub in subs
                ]
                embed.description = (embed.description or "") + (
                    "\n" + "\n".join(sub_lines) if sub_lines else ""
                )
            view = ManageFollowingView(subs)
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
            return

        # In a guild: check permissions
        from discord import Member

        perms = None
        if isinstance(interaction.user, Member):
            perms = interaction.user.guild_permissions  # type: ignore
        if not perms or not (perms.manage_guild or perms.manage_channels):
            await interaction.response.send_message(
                "You don't have permission to configure following in this server. "
                "You can invoke this command in a DM to configure personal message subscriptions.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id  # type: ignore
        subscriptions = get_all_in_guild(guild_id)
        if subscriptions:
            desc = "\n".join(
                [
                    f"- `{sub.service_type}`: `{sub.search_criteria}` in <#{getattr(sub, 'channel_id', 'unknown')}> with filters `{sub.filters}`"
                    for sub in subscriptions
                ]
            )
        else:
            desc = "No subscriptions configured in this guild."
        embed = discord.Embed(
            title="Manage Following", description=desc, color=discord.Color.blue()
        )
        view = ManageFollowingView(subscriptions)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SubscribeCog(bot))
