import re
import os
import logging
import discord

from discord.ext import commands

from utilities.database import retrieve_key_number, store_key_number


def get_current_changelog(file_path) -> (int, str):
    try:
        with open(file_path, "r") as file:
            content = file.read()
    except FileNotFoundError:
        logging.warning(f"Changelog file not found: {file_path}")
        try:
            with open("README.md", "r") as file:  # For local!
                content = file.read()
        except FileNotFoundError:
            return 1, "No changelog found"

    # Regular expression to find changelog sections
    changelog_pattern = re.compile(
        r"## Changelog (\d+)(.*?)(?=## Changelog \d+|$)", re.DOTALL
    )

    changelogs = changelog_pattern.findall(content)

    if not changelogs:
        return None, None

    # Extract the latest changelog number and content
    latest_changelog = changelogs[-1]
    changelog_number = int(latest_changelog[0])
    changelog_content = latest_changelog[1].strip()

    return changelog_number, changelog_content


class Changelog(commands.Cog, name="ChangeLogCog"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Check for new changelog on bot startup and DM all guild owners.
        """

        # Log all guilds and their owners
        self.logger.info(f"Bot is running in {len(self.bot.guilds)} guilds:")
        for guild in self.bot.guilds:
            owner = guild.owner
            if owner:
                self.logger.info(f"  - {guild.name} : {owner.name} ({owner.id})")
            else:
                self.logger.warning(f"  - {guild.name} : [No owner found]")

        self.last_log = retrieve_key_number("LAST_CHANGELOG", 0)

        changelog_path = "/app/README.md"

        # Load and parse changelog
        self.logger.info(f"Loading {changelog_path}")
        _d = get_current_changelog(changelog_path)
        cur_lognum = int(_d[0])
        cur_logstr = _d[1]

        self.logger.info(f"Changelog is currently {cur_lognum}/{self.last_log}.")
        self.logger.debug(f"Changelog content was: {cur_logstr}")

        if cur_lognum == self.last_log:
            self.logger.info("No new changelog to report.")
            return

        # Format the changelog message
        try:
            changelog_message = (
                f"# Fops Bot Update - Changelog {cur_lognum}\n\n"
                + cur_logstr.replace("{{version}}", self.bot.version)
                + f"\n\n*This message was sent to you because you own a server where Fops Bot is installed! Please direct feedback to Snowsune or vixi@snowsune.net!*"
            )
        except AttributeError:
            self.logger.error("Bot version is not set, skipping changelog.")
            return

        # Send to all guild owners
        sent_count = 0
        failed_count = 0
        owner_ids_messaged = (
            set()
        )  # Track unique owners (they might own multiple servers)

        for guild in self.bot.guilds:
            owner = guild.owner
            if not owner:
                self.logger.warning(f"Could not find owner for guild {guild.name}")
                failed_count += 1
                continue

            # Skip if we already messaged this owner
            if owner.id in owner_ids_messaged:
                self.logger.debug(
                    f"Skipping {owner.name} - already sent (owns more than one server)"
                )
                continue

            try:
                await owner.send(changelog_message)
                owner_ids_messaged.add(owner.id)
                sent_count += 1
                self.logger.info(f"Sent changelog to {owner.name} ({guild.name})")

            except discord.errors.Forbidden:
                self.logger.warning(
                    f"Could not DM {owner.name} - DMs disabled or blocked"
                )
                failed_count += 1
            except Exception as e:
                self.logger.error(f"Error sending to {owner.name}: {e}")
                failed_count += 1

        # Update the db after posting
        store_key_number("LAST_CHANGELOG", cur_lognum)

        self.logger.info(
            f"Changelog complete! Sent to {sent_count} owners, {failed_count} failed."
        )


async def setup(bot):
    await bot.add_cog(Changelog(bot))
