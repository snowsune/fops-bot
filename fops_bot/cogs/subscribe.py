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

# Load FurAffinity cookies from environment variables
FA_COOKIE_A = os.getenv("FA_COOKIE_A")
FA_COOKIE_B = os.getenv("FA_COOKIE_B")


def get_all_in_guild(guild_id: int) -> List[Subscription]:
    """Return all Subscription entries for a given guild."""
    with get_session() as session:
        return list(session.query(Subscription).filter_by(guild_id=guild_id).all())


class ManageFollowingView(discord.ui.View):
    def __init__(self, subscriptions: List[Subscription]):
        super().__init__(timeout=180)
        self.subscriptions = subscriptions

    @discord.ui.button(
        label="Add", style=discord.ButtonStyle.green, custom_id="add_following"
    )
    async def add_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # TODO: Show dropdown for service type, then modal for search/filters
        await interaction.response.send_message(
            "Add subscription (UI coming soon)", ephemeral=True
        )

    @discord.ui.button(
        label="Remove", style=discord.ButtonStyle.red, custom_id="remove_following"
    )
    async def remove_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # TODO: Show dropdown or modal to select and remove a subscription
        await interaction.response.send_message(
            "Remove subscription (UI coming soon)", ephemeral=True
        )


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
        guild_id = interaction.guild.id
        subscriptions = get_all_in_guild(guild_id)
        if subscriptions:
            desc = "\n".join(
                [
                    f"- `{sub.service_type}`: `{sub.search_criteria}` in <#{sub.channel_id}>"
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
