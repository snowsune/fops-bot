import os
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging

OWNER_UID = int(os.getenv("OWNER_UID", "0"))


class VixiThinks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.thinking_messages = {}  # message_id -> (channel_id, original_message_id)

        # Register the context menu command
        self.context_menu = app_commands.ContextMenu(
            name="Vixi Thinks", callback=self.vixi_thinks
        )
        self.bot.tree.add_command(self.context_menu)

    # Context only~ lets you know what vixi thinks!
    async def vixi_thinks(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        await interaction.response.send_message("Vixi is thinking...", ephemeral=True)

        owner = self.bot.get_user(OWNER_UID) or await self.bot.fetch_user(OWNER_UID)
        if not owner:
            await interaction.followup.send(
                "Ah! Couldn't connect to the vixisphere >:3", ephemeral=True
            )
            return

        # DM the owner with the original message content
        forwarded = await owner.send(
            f"**Forwarded from <#{interaction.channel.id}> by {interaction.user.mention}**\n"
            f"{message.content}\n\n"
            f"*(Don't forget to reply to this message!)*"
        )

        # Save mapping from the DM message to the original channel/message
        self.thinking_messages[forwarded.id] = (message.channel.id, message.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Only respond to DMs from the owner
        if message.guild is not None or message.author.id != OWNER_UID:
            return

        # Check if it's a reply to a tracked message
        if message.reference and message.reference.message_id:
            original = self.thinking_messages.get(message.reference.message_id)
            if original:
                channel_id, original_message_id = original
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    channel = await self.bot.fetch_channel(channel_id)
                try:
                    original_msg = await channel.fetch_message(original_message_id)
                    await original_msg.reply(f"**Vixi Thinks:** {message.content}")
                except discord.HTTPException:
                    await message.channel.send("Failed to reply to original message.")

                # Clean up
                del self.thinking_messages[message.reference.message_id]


async def setup(bot):
    await bot.add_cog(VixiThinks(bot))
