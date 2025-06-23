import os
import faapi  # type: ignore
import discord
import logging
from discord.ext import commands
from discord import app_commands
from typing import Optional
from requests.cookies import RequestsCookieJar
from datetime import datetime, timezone
from fops_bot.models import get_session, Subscription

# Load FurAffinity cookies from environment variables
FA_COOKIE_A = os.getenv("FA_COOKIE_A")
FA_COOKIE_B = os.getenv("FA_COOKIE_B")


class SubscribeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.fa_cookie_a = str(FA_COOKIE_A)
        self.fa_cookie_b = str(FA_COOKIE_B)

        if len(self.fa_cookie_a) < 10 or len(self.fa_cookie_b) < 10:
            self.logger.warning("FA cookies look short/invalid.")

    @app_commands.command(
        name="subscribe_fa", description="Subscribe to a FurAffinity userpage!"
    )
    async def subscribe_fa(
        self,
        interaction: discord.Interaction,
        username: str,
        channel: Optional[discord.TextChannel] = None,
    ):
        # Normalize username (trim and lowercase for matching)
        normalized_username = username.strip().lower()
        target_channel_id = channel.id if channel else interaction.channel.id
        target_guild_id = interaction.guild.id

        # 1. Enforce 10,000 active user limit and prevent duplicate subscriptions
        with get_session() as session:
            fa_count = (
                session.query(Subscription)
                .filter_by(service_type="FurAffinity")
                .count()
            )
            # Check for duplicate subscription
            duplicate = (
                session.query(Subscription)
                .filter(
                    Subscription.service_type == "FurAffinity",
                    Subscription.guild_id == target_guild_id,
                    Subscription.channel_id == target_channel_id,
                    Subscription.search_criteria.ilike(normalized_username),
                )
                .first()
            )
            if duplicate:
                await interaction.response.send_message(
                    f"Already subscribed to `{username}` in this channel.",
                    ephemeral=True,
                )
                return
            if fa_count >= 10000:
                await interaction.response.send_message(
                    f"FA bot activity limited for politeness ({fa_count} > 10,000), try again another time!",
                    ephemeral=True,
                )
                return

        # 2. Prepare cookies for faapi
        cookies = RequestsCookieJar()
        cookies.set("a", self.fa_cookie_a or "")
        cookies.set("b", self.fa_cookie_b or "")
        api = faapi.FAAPI(cookies)

        # 3. Validate username and get latest post
        try:
            gallery, _ = api.gallery(username, 1)
            if not gallery:
                raise ValueError("No submissions found or user does not exist.")
            latest_submission = gallery[0]
            latest_post_id = latest_submission.id
        except Exception as e:
            await interaction.response.send_message(f"FA error: {e}", ephemeral=True)
            return

        # 4. Store subscription in DB
        with get_session() as session:
            sub = Subscription(
                service_type="FurAffinity",
                user_id=interaction.user.id,
                subscribed_at=datetime.now(timezone.utc),
                guild_id=target_guild_id,
                channel_id=target_channel_id,
                search_criteria=normalized_username,
                last_reported_id=latest_post_id,
            )
            session.add(sub)
            session.commit()

        await interaction.response.send_message(
            f"Attached FA user feed for `{username}` to <#{target_channel_id}>",
            ephemeral=True,
        )

    @app_commands.command(
        name="subscribe_booru", description="Subscribe to a booru search."
    )
    async def subscribe_booru(
        self,
        interaction: discord.Interaction,
        search: str,
        channel: Optional[discord.TextChannel] = None,
        service: str = "e6",
    ):
        # TODO: Implement booru/e6 subscription logic
        await interaction.response.send_message(
            f"Subscribed to {service} search: {search}", ephemeral=True
        )

    # Optionally, add unsubscribe and list commands here


async def setup(bot):
    await bot.add_cog(SubscribeCog(bot))
