# FOSNHU
# 2021, Fops Bot
# MIT License

import os
import sys
import asyncio
import logging
import random
import colorlog
import time
import signal

import discordhealthcheck

import discord
from discord import Intents, app_commands
from discord.ext import commands

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up colorlog for colored logs
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)s:%(name)s: %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
)

# Set log level based on DEBUG env variable
debug_env = str(os.environ.get("DEBUG", "0")).lower() in ("true", "1", "t", "yes")
log_level = logging.DEBUG if debug_env else logging.INFO
logging.basicConfig(level=log_level, handlers=[handler])

# Mute discord.py logs except warnings/errors
discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.WARNING)
for h in discord_logger.handlers[:]:
    discord_logger.removeHandler(h)


class FopsBot:
    def __init__(self):
        # Intents (new iirc)
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.messages = True
        intents.reactions = True
        intents.members = True
        intents.message_content = True

        self.version = None

        # Some local memory flags
        self.dbReady = False

        # Create our discord bot
        self.version = str(os.environ.get("GIT_COMMIT"))  # Currently running version
        self.bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
        # Store version on bot instance for cogs to access
        setattr(self.bot, "version", self.version)

        # Remove legacy help command
        self.bot.remove_command("help")

        # Get the build commit that the code was built with.
        # Find out if we're running in debug mode, or not.
        self.debug = str(os.environ.get("DEBUG", "0")).lower() in (
            "true",
            "1",
            "t",
            "yes",
        )

        # Append our workdir to the path (for importing modules)
        self.workdir = "/app/fops_bot/"
        sys.path.append(self.workdir)

        # Append some extra information to our discord bot
        # self.version is available on the FopsBot instance, not the bot object

        self.start_time = time.time()

        # DB Setup
        try:
            logging.info("Configuring DB and running migrations")
            self.dbReady = True
        except Exception as e:
            logging.error(f"Could not configure the DB! Error was {e}")
            self.dbReady = False
        finally:
            logging.info("Done configuring DB")

    async def load_cogs(self):
        # Cog Loader!
        logging.info("Loading cogs...")

        import importlib
        import pkgutil

        package = "cogs"
        cogs_pkg = importlib.import_module(package)
        cogs_dir = cogs_pkg.__path__[0]

        for _, modname, ispkg in pkgutil.iter_modules([cogs_dir]):
            if not ispkg and not modname.startswith("_"):
                try:
                    await self.bot.load_extension(f"cogs.{modname}")
                except Exception as e:
                    logging.fatal(f"Error loading {modname} as a cog, error: {e}")
                    raise e
        logging.info("Done loading cogs")

    # Standalone on_ready event for the bot
    async def on_ready_logic(self):
        # Start health monitoring
        logging.info(
            "Preparing external monitoring (using discordhealthcheck https://pypi.org/project/discordhealthcheck/)"
        )
        self.healthcheck_server = await discordhealthcheck.start(self.bot)
        logging.info("Done prepping external monitoring")
        await self.bot.tree.sync()

    async def on_message(self, ctx):
        # hehe, sneaky every time
        logging.info(ctx)

    async def start_bot(self):
        logging.info(f"Using version {self.version}")

        if not self.dbReady:
            logging.error("Database not ready. Bot will not start.")
            return

        # Begin the cog loader
        await self.load_cogs()

        # Register old on_ready in the new discord.py way
        @self.bot.event
        async def on_ready():
            await self.on_ready_logic()

        # Register shutdown handler
        @self.bot.event
        async def on_disconnect():
            from utilities.influx_metrics import close_client
            close_client()

        # Run the discord bot using our token.
        await self.bot.start(str(os.environ.get("BOT_TOKEN")))

    def run(self):
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            from utilities.influx_metrics import close_client
            close_client()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        asyncio.run(self.start_bot())


if __name__ == "__main__":
    bot = FopsBot()
    bot.run()
