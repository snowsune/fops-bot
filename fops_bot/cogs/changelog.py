import re
import os
import logging
import discord

from discord.ext import commands, tasks

from utilities.database import retrieve_key, store_key


def get_current_changelog(file_path) -> (int, str):
    with open(file_path, "r") as file:
        content = file.read()

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


class Changelog(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.last_log = retrieve_key("LAST_CHANGELOG", 0)

        changelog_path = "/app/README.md"

        # Crack the data we need
        logging.info(f"Loading {changelog_path}")
        _d = get_current_changelog(changelog_path)
        cur_lognum = _d[0]
        cur_logstr = _d[1]

        logging.info(
            f"Changelog is currently {cur_lognum}/{self.last_log}. Content was: {cur_logstr}"
        )

        if cur_lognum == self.last_log:
            # If they match, we're done and we can pack up
            logging.info("No new changelog to report.")
            return

        # If they dont match, we need to post the last changelog and update!
        channel = self.bot.get_channel(
            int(os.environ.get("ALERT_CHAN_ID", "00000000000"))
        )

        if channel == None:
            logging.error("Could not fetch alert channel to post changelog!")
            return

        # Filter any keywords in
        cur_logstr = cur_logstr.replace("{{version}}", self.bot.version)

        # Post the changelog
        await channel.send(cur_logstr)

        # Update the db
        store_key("LAST_CHANGELOG", cur_lognum)

        logging.info("Changelog done!")


async def setup(bot):
    await bot.add_cog(Changelog(bot))
