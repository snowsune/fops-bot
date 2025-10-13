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
        description="Manage your followed FA/E6 feeds (moved to web!)",
    )
    async def manage_following(self, interaction: discord.Interaction):
        """
        This command has been moved to the web dashboard!
        """
        embed = discord.Embed(
            title="🌐 This function is no longer used!",
            description=(
                "Subscription management has moved to the web dashboard for a better experience!\n\n"
                "**Visit:** [snowsune.net/fops](https://snowsune.net/fops/redirect/)\n\n"
                "You can manage all your subscriptions, filters, and settings there."
            ),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SubscribeCog(bot))
