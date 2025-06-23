import discord
from discord.ext import commands
from discord import app_commands
import logging


class SubscribeCog(commands.Cog, name="SubscribeCog"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @app_commands.command(
        name="subscribe_fa", description="Subscribe to a FurAffinity user."
    )
    async def subscribe_fa(
        self,
        interaction: discord.Interaction,
        username: str,
        channel: discord.TextChannel = None,
    ):
        # TODO: Implement FurAffinity subscription logic
        await interaction.response.send_message(
            f"Subscribed to FurAffinity user: {username}", ephemeral=True
        )

    @app_commands.command(
        name="subscribe_booru", description="Subscribe to a booru search."
    )
    async def subscribe_booru(
        self,
        interaction: discord.Interaction,
        search: str,
        channel: discord.TextChannel = None,
        service: str = "e6",
    ):
        # TODO: Implement booru/e6 subscription logic
        await interaction.response.send_message(
            f"Subscribed to {service} search: {search}", ephemeral=True
        )

    # Optionally, add unsubscribe and list commands here


async def setup(bot):
    await bot.add_cog(SubscribeCog(bot))
