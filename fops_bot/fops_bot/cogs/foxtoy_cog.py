# 2024, Fops Bot
# MIT License

import discord
import logging
import asyncio
import time
import random
import pytz
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks
from utilities.database import store_key, retrieve_key
from utilities.common import seconds_until
from utilities.database import (
    retrieve_key_number,
    store_key_number,
)

# Constants
ROLE = "1371890734377996319"  # Fox Toy
GUILD = "1153521286086148156"  # Vixi's Den
CHAN = "1354254133330317382"  # Vixens Lounge
ADMIN_ROLE = "1218272502434762792"  # Moderator
FOX_ROLE = "1354290953661452429"  # Vixen


class FoxtoyCog(commands.Cog, name="FoxtoyCog"):
    def __init__(self, bot):
        self.bot = bot
        self.localtz = pytz.timezone("US/Eastern")
        self.logger = logging.getLogger(__name__)

    async def cog_unload(self):
        self.role_rotation.cancel()

    @tasks.loop(minutes=10)  # Check every 10 minutes
    async def role_rotation(self):
        self.logger.info("Foxtoy role rotation task running")

        # Check if we need to rotate immediately
        last_change = retrieve_key_number("last_fox_toy_change", 0)
        current_time = int(time.time())
        time_since_change = current_time - last_change

        if time_since_change > 7 * 24 * 60 * 60:  # More than 7 days ago
            self.logger.warning("Role is out of date, rotating immediately")
        else:
            # Calculate time until next Sunday
            now = datetime.now(self.localtz)
            days_until_sunday = (6 - now.weekday()) % 7
            if (
                days_until_sunday == 0 and now.hour >= 0
            ):  # If it's already Sunday, wait until next week
                days_until_sunday = 7

            next_sunday = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=days_until_sunday)
            wait_seconds = (next_sunday - now).total_seconds()
            self.logger.info(f"Waiting {wait_seconds} seconds until next Sunday")
            await asyncio.sleep(wait_seconds)

        # Get the guild
        guild = self.bot.get_guild(int(GUILD))
        if not guild:
            self.logger.error("Could not find guild")
            return

        # Get the role
        role = guild.get_role(int(ROLE))
        if not role:
            self.logger.error("Could not find role")
            return

        # Get the channel
        channel = guild.get_channel(int(CHAN))
        if not channel:
            self.logger.error("Could not find channel")
            return

        # Get all members who don't have admin or fox role
        eligible_members = []
        for member in guild.members:
            # Skip bots
            if member.bot:
                continue
            # Skip if member has admin role (if admin role is set)
            if ADMIN_ROLE and any(role.id == int(ADMIN_ROLE) for role in member.roles):
                continue
            # Skip if member has fox role (if fox role is set)
            if FOX_ROLE and any(role.id == int(FOX_ROLE) for role in member.roles):
                continue
            eligible_members.append(member)

        if not eligible_members:
            self.logger.error("No eligible members found")
            return

        # Remove role from current holder
        current_holder = None
        for member in guild.members:
            if role in member.roles:
                current_holder = member
                await member.remove_roles(role)
                break

        # Select new random member
        new_holder = random.choice(eligible_members)
        await new_holder.add_roles(role)

        # Store the change
        store_key("last_fox_toy", str(new_holder.id))
        store_key_number("last_fox_toy_change", int(time.time()))

        # Announce the change
        await channel.send(
            f"Okay vixens! You have a new <@&{ROLE}> to play with! Say hello to {new_holder.mention}!"
        )

    @commands.Cog.listener()
    async def on_ready(self):
        self.role_rotation.start()
        self.logger.info("Foxtoy role rotation task started")


async def setup(bot):
    await bot.add_cog(FoxtoyCog(bot))
