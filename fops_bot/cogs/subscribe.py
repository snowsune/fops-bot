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
        """
        Manages your subscriptions to [furaffinity](https://www.furaffinity.net/), [e621](https://e621.net/), [booru.kitsunehosting.net](https://booru.kitsunehosting.net/) and more!

        Run this command anywhere to get started. You can attach a follower command to any channel
        in the group you're currently in. or a PM

        You can use both positive and negative filters for sorting. Heres some examples:

         - `-irl`         Any post that does not contain `irl`
         - `rating:safe`  Only posts that have a safe rating
         - ` `            Any post
         - `vulpine`      Only posts with vulpine as a tag
        """

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
                sub_lines = []
                for sub in subs:
                    if sub.last_ran is not None:
                        last_ran_str = f"<t:{sub.last_ran}:R>"
                    else:
                        last_ran_str = "never"
                    sub_lines.append(
                        f"- `{sub.service_type}`: `{sub.search_criteria}` with filters `{sub.filters}` (last checked: {last_ran_str})"
                    )
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
            desc_lines = []
            for sub in subscriptions:
                if sub.last_ran is not None:
                    last_ran_str = f"<t:{sub.last_ran}:R>"
                else:
                    last_ran_str = "never"
                desc_lines.append(
                    f"- `{sub.service_type}`: `{sub.search_criteria}` in <#{getattr(sub, 'channel_id', 'unknown')}> with filters `{sub.filters}` (last checked: {last_ran_str})"
                )
            desc = "\n".join(desc_lines)
        else:
            desc = "No subscriptions configured in this guild."
        embed = discord.Embed(
            title="Manage Following", description=desc, color=discord.Color.blue()
        )
        view = ManageFollowingView(subscriptions)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SubscribeCog(bot))
