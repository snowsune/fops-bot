# FOSNHU
# 2021, Fops Bot
# MIT License

import os
import sys
import asyncio
import logging
import random

import discordhealthcheck

import discord
from discord import Intents
from discord.ext import commands

from .utilities.database import init_db


class FopsBot:
    def __init__(self):
        # Intents (new iirc)
        intents = Intents(messages=True, guilds=True)
        intents.message_content = True

        # Create our discord bot
        self.bot = commands.Bot(command_prefix="^", intents=intents)

        # Remove legacy help command
        self.bot.remove_command("help")

        # Register python commands
        self.bot.on_ready = self.on_ready
        # self.bot.on_message = self.on_message

        # Get the build commit that the code was built with.
        self.version = str(os.environ.get("GIT_COMMIT"))  # Currently running version
        # Find out if we're running in debug mode, or not.
        self.debug = str(os.environ.get("DEBUG")).lower() in ("true", "1", "t")

        # Append our workdir to the path (for importing modules)
        self.workdir = "/app/fops_bot/"
        sys.path.append(self.workdir)

        # Setup logging.
        if self.debug:
            logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
            logging.debug("Running in debug mode.")
        else:
            logging.basicConfig(stream=sys.stderr, level=logging.INFO)
            logging.info("Running in prod mode.")

        # Append some extra information to our discord bot
        self.bot.version = self.version  # Package version with bot

    async def load_cogs(self):
        # Cog Loader!
        logging.info("Loading cogs...")
        for filename in os.listdir(self.workdir + "cogs"):
            logging.info(f"Found file {filename}, loading as extension.")
            if filename.endswith(".py"):
                try:
                    await self.bot.load_extension(f"cogs.{filename[:-3]}")
                except Exception as e:
                    logging.fatal(f"Error loading {filename} as a cog, error: {e}")
        logging.info("Done loading cogs")

    async def on_ready(self):
        # Start health monitoring
        logging.info(
            "Preparing external monitoring (using discordhealthcheck https://pypi.org/project/discordhealthcheck/)"
        )
        self.healthcheck_server = await discordhealthcheck.start(self.bot)
        logging.info("Done prepping external monitoring")

        # DB Setup
        try:
            logging.info("Configuring DB")
            self.bot.dbReady = init_db()
        except Exception as e:
            logging.error(f"Could not configure the DB! Error was {e}")
            self.bot.dbReady = False
        finally:
            logging.info("Done configuring DB")

        await self.bot.tree.sync()

    async def on_message(self, ctx):
        # hehe, sneaky every time
        logging.info(ctx)

    async def start_bot(self):
        logging.info(f"Using version {self.version}")

        # Begin the cog loader
        await self.load_cogs()

        # Run the discord bot using our token.
        await self.bot.start(str(os.environ.get("BOT_TOKEN")))

    def run(self):
        asyncio.run(self.start_bot())
