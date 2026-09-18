import logging

import discord
from discord import app_commands
from discord.ext import commands

# Guilds where ?quicklinks are active
QUICKLINK_GUILDS = {
    505468527503867904,
    1153521286086148156,
}

# Map ?key -> response text (add more entries here)
QUICK_LINKS = {
    "matrix": "https://matrix.kitsunehosting.net/",
}


class QuicklinksCog(commands.Cog, name="QuicklinksCog"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @commands.Cog.listener("on_message")
    async def quicklink_listener(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        if message.guild.id not in QUICKLINK_GUILDS:
            return

        content = message.content.strip()
        if not content.startswith("?"):
            return

        key = content[1:].split()[0].lower() if content[1:].strip() else ""
        if key not in QUICK_LINKS:
            return

        await message.reply(QUICK_LINKS[key])

    @app_commands.command(
        name="show_quick_links",
        description="List all configured ?quicklinks",
    )
    async def show_quick_links(self, interaction: discord.Interaction):
        if not QUICK_LINKS:
            await interaction.response.send_message(
                "No quicklinks configured.", ephemeral=True
            )
            return

        lines = [f"`?{key}` → {url}" for key, url in sorted(QUICK_LINKS.items())]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot):
    await bot.add_cog(QuicklinksCog(bot))
