import os
import logging
import requests
import discord
from discord.ext import commands


class PushpinCog(commands.Cog, name="PushpinCog"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.connector_key = os.environ.get("CONNECTOR_KEY", "iamnotacrook")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """
        Monitor for pushpin emoji reactions and make API call if server owner adds it.
        """

        # Check if the reaction is a pushpin emoji
        if str(reaction.emoji) != "📌":
            return

        # Check if the user is a bot (ignore bot reactions)
        if user.bot:
            return

        # Check if the user is me~
        if str(user.id) != os.getenv("OWNER_UID"):
            logging.info(f"User {user.name} ({user.id}) is not the owner, ignoring")
            return

        self.logger.info(
            f"Server owner {user.name} ({user.id}) added pushpin reaction in {reaction.message.guild.name}"
        )

        # Make the API call
        await self.send_quote_webhook(user, reaction.message)

        # Add a confirmation reaction
        await reaction.message.add_reaction("📌")

    async def send_quote_webhook(self, user, message):
        """
        Send the qoute to my server!
        """
        try:
            payload = {
                "content": message.content,
                "user": user.display_name if user.display_name else user.name,
                "discord_id": str(user.id),
                "key": self.connector_key,
            }

            response = requests.post(
                "https://snowsune.net/quotes/webhook/",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                self.logger.info(
                    f"Successfully sent quote webhook for user {user.name}"
                )
            else:
                self.logger.error(
                    f"Failed to send quote webhook. Status: {response.status_code}, Response: {response.text}"
                )

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error sending quote webhook: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in send_quote_webhook: {e}")


async def setup(bot):
    await bot.add_cog(PushpinCog(bot))
