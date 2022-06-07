# FOSNHU
# 2021, Fops Bot
# MIT License


import discord
import logging

from discord.ext import commands


class ToolCog(commands.Cog, name="Tools"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        status_channel = self.bot.get_channel(963065508628926477)

        await self.bot.get_guild(963065508628926474).me.edit(nick="Fops")

        await status_channel.send(
            f"Fops Bot version `{self.bot.version}` just restarted."
        )

    @commands.command()
    async def version(self, ctx, *, member: discord.Member = None):
        """
        Prints the revision/version.

        Ex: .version

        Written by Joe.
        """

        await ctx.send(f"I am running version `{self.bot.version}`.")

    @commands.command()
    async def feature(self, ctx, *args):
        """
        Allows users to request a feature

        Ex: .feature Give the bot a self destruct command!

        Written by Joe.
        """

        title = "+".join(args)

        await ctx.send(
            f"https://github.com/KenwoodFox/FOpS-Bot/issues/new?labels=feature&title={title}&body=Describe+your+feature+here+please!"
        )


def setup(bot):
    bot.add_cog(ToolCog(bot))
