import discord
import logging
import asyncio
from discord.ext import commands


class TempRoleAssignCog(commands.Cog, name="TempRoleAssignCog"):
    def __init__(self, bot):
        self.bot = bot
        self.target_guild_id = 1153521286086148156
        self.check_role_id = 1219310732944998591
        self.assign_role_id = 1384258724939698459
        self.has_run = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self.has_run:
            return

        logging.info("Starting temporary role assignment task...")
        guild = self.bot.get_guild(self.target_guild_id)

        if not guild:
            logging.error(f"Could not find guild with ID {self.target_guild_id}")
            return

        check_role = guild.get_role(self.check_role_id)
        assign_role = guild.get_role(self.assign_role_id)

        if not check_role or not assign_role:
            logging.error("Could not find one or both roles")
            return

        member_count = len(guild.members)
        processed = 0

        for member in guild.members:
            try:
                if check_role not in member.roles:
                    await member.add_roles(assign_role)
                    logging.info(f"Assigned role to {member.name} ({member.id})")
                processed += 1
                logging.info(f"Processed {processed}/{member_count} members")
                await asyncio.sleep(5)  # 5 second delay between members
            except discord.Forbidden:
                logging.error(f"Missing permissions to modify roles for {member.name}")
            except Exception as e:
                logging.error(f"Error processing member {member.name}: {str(e)}")

        logging.info("Temporary role assignment task completed")
        self.has_run = True


async def setup(bot):
    await bot.add_cog(TempRoleAssignCog(bot))
