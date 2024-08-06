# 2023, Fops Bot
# MIT License

import psycopg
import discord
import logging
import asyncio
import time
import random
import pytz
import os
import python_weather
import yaml
import shutil

from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone

from utilities.common import seconds_until
from utilities.database import retrieve_key, store_key


class HolesCog(commands.Cog, name="HolesCog"):
    def __init__(self, bot):
        self.bot = bot
        self.localtz = pytz.timezone("US/Eastern")

        # Define paths
        self.config_path = "/app/config/hole_config.yaml"
        self.template_path = "/app/fops_bot/templates/hole_config.yaml"

        # Ensure config exists
        self.ensure_config_exists(self.config_path, self.template_path)

        # Load YAML config
        self.config = self.load_config(self.config_path)
        self.dynamic_users_index = {}

        # Ids
        self.default_id = "000000000000000"
        self.base_hole_user_key = "hole_user_id"
        self.base_hole_user_time_key = "hole_user_last_changed"
        self.base_hole_user_chan_map_key = "hole_channel_map"

    @commands.Cog.listener()
    async def on_ready(self):
        # Start daily task to rotate dynamic users
        self.rotate_dynamic_users.start()

    def ensure_config_exists(self, config_path, template_path):
        if not os.path.exists(config_path):
            logging.info(f"Config file missing, copying template from {template_path}")
            shutil.copy(template_path, config_path)

    def load_config(self, path):
        with open(path, "r") as file:
            return yaml.safe_load(file)

    @commands.Cog.listener("on_message")
    async def holeInTheWallListener(self, msg: discord.Message):
        logging.debug(f"Hole In the wall got {msg}")

        # Shush of OOC
        if msg.content[0] == "(":
            return

        # Check if the message is in a static channel
        for static_pair in self.config["static"]:
            chan, user = map(int, static_pair)

            # If the msg is a private dm check the user id
            if isinstance(msg.channel, discord.channel.DMChannel):
                if msg.author.id == user:
                    await self.returning_message(msg, msg.author.id, chan)
                    return

            # If its a public channel just check the chan_id
            if msg.channel.id == chan:
                await self.forward_message(msg, user)
                return

        # Check if the message is in a dynamic channel
        for server_config in self.config["dynamic"]:
            # Check if in-guild (in a server) AND check if the guild_id matches
            if msg.guild and msg.guild.id == int(server_config["guild_id"]):

                # Next check if the channel ID matches
                if msg.channel.id == int(server_config["chan_id"]):

                    user_id = int(
                        retrieve_key(f"{self.base_hole_user_key}_{msg.guild.id}")
                    )
                    await self.forward_message(msg, user_id)
                    return

        # Check if the message is a PM
        if isinstance(msg.channel, discord.channel.DMChannel):
            user_id = msg.author.id
            await self.returning_message(msg, user_id)
            return

    async def returning_message(self, msg, user_id, chan_id=None):
        # If you dont specify a channel id, this function will look up the mapping in the DB
        if not chan_id:
            channel_id = retrieve_key(f"{self.base_hole_user_chan_map_key}_{user_id}")
        else:
            channel_id = chan_id

        if channel_id:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                await channel.send(f"*{msg.author.display_name}:*\n{msg.content}")
                await msg.add_reaction("📬")
            else:
                await msg.add_reaction("❌")

    async def forward_message(self, msg, user_id):
        if msg.author.bot:
            return

        if isinstance(msg.channel, discord.channel.DMChannel):
            if msg.author.id == user_id:
                holeChan = self.bot.get_channel(msg.channel.id)
                await holeChan.send(msg.content)
                await msg.add_reaction("📬")
            else:
                await msg.add_reaction("❌")
        else:
            recipient = await self.bot.fetch_user(user_id)
            if recipient is None:
                await msg.add_reaction("❌")
                return
            else:
                await recipient.send(f"*Somebody..*\n{msg.content}")
                await msg.add_reaction("📬")

    def isCurrentUserStale(self):
        # Helper function to check if we need to update the current user

        # Iter all servers
        for server_config in self.config["dynamic"]:
            # Retrieve value
            curId = retrieve_key(
                f"{self.base_hole_user_key}_{server_config['guild_id']}",
                self.default_id,
            )
            userTime = retrieve_key(
                f"{self.base_hole_user_time_key}_{server_config['guild_id']}"
            )

            # Check if default id
            if curId == self.default_id:
                logging.info("User ID is stale because the value is default")
                return True  # Value is default and needs to be updated

            if userTime == None:
                logging.warning(
                    "User ID is stale because the time has not been set????????"
                )
                return (
                    True  # Not sure how we would get here but, yeah we'd need to update
                )

            if int(time.time()) - int(userTime) > (21600):
                logging.info(
                    f"User ID is stale because the time has expired, {int(time.time()) - int(userTime)} > {21600}"
                )
                return True  # If there is a more than 6hr difference

        return False

    @tasks.loop(seconds=10)
    async def rotate_dynamic_users(self):
        # populate if needed
        if not self.isCurrentUserStale():
            logging.info(
                f"{self.qualified_name}: Waiting for 7AM to cycle next user",
            )
            wait = seconds_until(7, 00)  # Wait here till 7am
            await asyncio.sleep(wait)

        # Cycle user
        logging.info(
            f"{self.qualified_name}: Cycling user",
        )

        users = self.fetch_dynamic_users()
        for server_config in self.config["dynamic"]:
            guild_users = [
                u
                for u in users
                if u[0] == server_config["guild_id"]
                and u[1] == server_config["chan_id"]
            ]
            if not guild_users:
                continue

            user = random.choice(guild_users)
            user_id, fluff = user[2], user[3]

            # Update db
            store_key(
                f"{self.base_hole_user_key}_{server_config['guild_id']}",
                user_id,
            )
            store_key(
                f"{self.base_hole_user_time_key}_{server_config['guild_id']}",
                str(int(time.time())),
            )
            store_key(
                f"{self.base_hole_user_chan_map_key}_{user_id}",
                server_config["chan_id"],
            )

            chan_id = int(server_config["chan_id"])
            channel = self.bot.get_channel(chan_id)
            if channel:
                await channel.send(f"*{fluff}*")

    @rotate_dynamic_users.before_loop
    async def before_rotate_dynamic_users(self):
        logging.info(
            f"{self.qualified_name}: Waiting for bot to be ready",
        )
        await self.bot.wait_until_ready()
        logging.debug(f"{self.qualified_name}: Bot is ready")

    # ===================
    # Commands
    # ===================

    @app_commands.command(
        name="register", description="Register for the random-hole in this guild"
    )
    @app_commands.describe(fluff="A little sneak to display when you're chosen~")
    async def register(self, interaction: discord.Interaction, fluff: str):
        guild_id = str(interaction.guild.id)
        chan_id = str(interaction.channel.id)
        user_id = str(interaction.user.id)

        if isinstance(interaction.channel, discord.channel.DMChannel):
            await interaction.response.send_message("Must use in a guild!", ephemeral=True)
            return

        conn = psycopg.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
        )

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dynamic_users (guild_id, chan_id, user_id, fluff)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (guild_id, chan_id, user_id) DO NOTHING
            """,
            (guild_id, chan_id, user_id, fluff),
        )
        conn.commit()
        cur.close()
        conn.close()

        await interaction.response.send_message(
            f"Registered for the hole with fluff: {fluff}", ephemeral=True
        )

    @app_commands.command(
        name="deregister", description="Deregister from the hole in this guild"
    )
    async def deregister(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        chan_id = str(interaction.channel.id)
        user_id = str(interaction.user.id)

        if isinstance(interaction.channel, discord.channel.DMChannel):
            await interaction.response.send_message("Must use in a guild!", ephemeral=True)
            return

        conn = psycopg.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
        )

        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM dynamic_users
            WHERE guild_id = %s AND user_id = %s
            """,
            (guild_id, user_id),
        )
        conn.commit()
        cur.close()
        conn.close()

        await interaction.response.send_message(
            "Deregistered from the hole", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(HolesCog(bot))
