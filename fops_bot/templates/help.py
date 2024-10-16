from discord import app_commands
from discord.ext import commands
from utilities.database import is_feature_enabled  # DB helper


class GlobalHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            self.bot.tree.add_command(self.help_command, guild=guild)

    @app_commands.command(name="help", description="A simple and useful help command")
    async def help_command(self, ctx):
        # Guild ID
        guild_id = ctx.guild.id

        # Commands to hide from view
        hidden_cogs = [
            "toolscog",
            "globalhelp",
        ]

        help_message = "Here are the available commands:\n"

        for cog_name, cog in self.bot.cogs.items():
            # Skip if we ignore checking
            feature_enabled = is_feature_enabled(guild_id, cog_name.lower())

            if feature_enabled:
                help_message += f"\n**{cog_name}**\n"
                for command in cog.get_commands():
                    help_message += f"/{command.name} {command.signature}\n"
            else:
                help_message += f"\n**{cog_name}** is disabled in this guild. Ask an admin to enable it using `/enable_{cog_name.lower()}`.\n"

        await ctx.response.send_message(help_message, ephemeral=True)


async def setup(bot):
    await bot.add_cog(GlobalHelp(bot))
