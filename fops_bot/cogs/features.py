import discord
import logging

from discord import app_commands
from discord.ext import commands, tasks

from fops_bot.database.database import set_feature, get_all_features, Session


class FeatureCog(commands.Cog, name="FeatureCog"):
    def __init__(self, bot):
        self.bot = bot

        self.session = Session()

    @app_commands.command(name="enable_feature")
    async def enable_feature(self, ctx: discord.Interaction, feature_name: str):
        set_feature(self.session, str(ctx.guild.id), feature_name, enabled=True)
        await ctx.send(f"Feature `{feature_name}` enabled.")

    @app_commands.command(name="list_features")
    async def list_features(self, ctx: discord.Interaction):
        logging.info(f"Listing features for {ctx.author.name}")
        features = get_all_features(self.session, str(ctx.guild.id))
        feature_list = "\n".join(
            [
                f"{name}: {'Enabled' if state else 'Disabled'}"
                for name, state in features.items()
            ]
        )
        await ctx.send(f"Features:\n{feature_list}")

    @app_commands.command(name="ping")
    async def ping(self, ctx: discord.Interaction):
        logging.info(f"Ping from {ctx.author.name}")

        await ctx.send("Pong")


async def setup(bot):
    await bot.add_cog(FeatureCog(bot))
