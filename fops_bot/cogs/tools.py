import discord
import logging
import random

from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands

from utilities.database import store_key, retrieve_key


class ToolCog(commands.Cog, name="ToolsCog"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="version")
    async def version(self, ctx: discord.Interaction):
        """
        Prints the revision/version.
        """

        dbstatus = "Unknown"
        vc = None

        try:
            if self.bot.dbReady:
                try:
                    vc = retrieve_key("version_count", 0)
                    logging.info(f"Retreived vc as {vc}")
                    dbstatus = "Ready"
                except Exception as e:
                    logging.error(f"Error retrieving key, error was {e}")
                    dbstatus = "Not Ready (connected but cant retrieve now)"

                store_key("version_count", int(vc) + 1)
            else:
                dbstatus = "Not Ready"
        except Exception as e:
            logging.error(f"Couldn't check db at all, error was {e}")

        await ctx.response.send_message(
            f"I am running version `{self.bot.version}`. DB is `{dbstatus}`, access `{vc}`"
        )

    @commands.command()
    @commands.guild_only()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: Optional[Literal["~", "*", "^"]] = None,
    ) -> None:
        """
        From here https://gist.github.com/AbstractUmbra/a9c188797ae194e592efe05fa129c57f
        """
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @app_commands.command(name="roll")
    @app_commands.describe(
        dice="The dice to roll in the format 'xdy' where x is the number of dice and y is the number of sides"
    )
    async def roll(self, ctx: discord.Interaction, dice: str):
        """
        Rolls a dice in the format 'xdy'.
        """
        try:
            num, sides = map(int, dice.lower().split("d"))
            if num <= 0 or sides <= 0:
                raise ValueError
        except ValueError:
            await ctx.response.send_message(
                "Invalid dice format. Use 'xdy' where x is the number of dice and y is the number of sides, e.g., '2d6'."
            )
            return

        rolls = [random.randint(1, sides) for _ in range(num)]
        total = sum(rolls)
        await ctx.response.send_message(f"Rolls: {rolls}\nTotal: {total}")


async def setup(bot):
    await bot.add_cog(ToolCog(bot))
