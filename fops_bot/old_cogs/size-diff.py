import discord
import logging
from discord import app_commands
from discord.ext import commands

"""
Really really simple cog, just grabs my size-diff website.
"""


class SizeDiffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="size_diff",
        description="Get the link to the size diff calculator.",
    )
    async def get_size_diff_link(self, interaction: discord.Interaction):
        view = HeightConversionView()
        await interaction.response.send_message(
            "https://size-diff.kitsunehosting.net/",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(SizeDiffCog(bot))
