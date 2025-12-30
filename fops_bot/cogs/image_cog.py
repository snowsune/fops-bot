import io
import asyncio
import discord
import logging

from discord import app_commands
from discord.ext import commands
from utilities.image_utils import (
    apply_image_task,
    load_image_from_bytes,
    save_image_to_bytes,
    IMAGE_TASKS,
)

from typing import Optional

# Just makes sure we decorate where the image_tasks go, cool python!
import utilities.image_tasks


class TaskSelectView(discord.ui.View):
    """View with select dropdown for task selection."""

    def __init__(
        self, tasks: list[str], requires_attachment: bool, message: discord.Message
    ):
        super().__init__(timeout=300)
        self.tasks = tasks
        self.requires_attachment = requires_attachment
        self.message = message
        self.followup_message: Optional[discord.Message] = None

        # Add select dropdown
        options = [discord.SelectOption(label=task, value=task) for task in tasks]
        self.select = discord.ui.Select(
            placeholder="Select a tool...",
            options=options[:25],  # Discord limit
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        """Handle task selection."""
        task_name = self.select.values[0]

        # Remove the dropdown view to acknowledge the interaction without showing "thinking..."
        # This responds to the interaction by editing the message
        await interaction.response.edit_message(view=None)

        # The followup message (dropdown) that we'll delete after processing
        thinking_msg = self.followup_message

        cog = interaction.client.get_cog("ImageCog")
        if cog:
            await cog.process_image_task(
                interaction, task_name, self.message, thinking_msg
            )
        else:
            await interaction.followup.send(
                "Error: ImageCog not found.", ephemeral=True
            )


class ImageCog(commands.Cog, name="ImageCog"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.register_context_menus()

    def register_context_menus(self):
        """Register Fops Image and Fops Text context menu commands."""
        # Fops Image - for tasks requiring attachments
        image_menu = app_commands.ContextMenu(
            name="Fops Image",
            callback=self.show_image_modal,
        )
        self.bot.tree.add_command(image_menu)

        # Fops Text - for text-based tasks
        text_menu = app_commands.ContextMenu(
            name="Fops Text",
            callback=self.show_text_modal,
        )
        self.bot.tree.add_command(text_menu)

    async def show_image_modal(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """Show modal with task selection for image tasks."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Get tasks that require attachments
        tasks = [
            name
            for name, metadata in IMAGE_TASKS.items()
            if metadata.get("requires_attachment", True)
        ]

        if not tasks:
            await interaction.followup.send("No image tasks available.", ephemeral=True)
            return

        view = TaskSelectView(tasks, requires_attachment=True, message=message)
        followup_msg = await interaction.followup.send(
            "Select an image tool:", view=view, ephemeral=True
        )
        view.followup_message = followup_msg

    async def show_text_modal(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """Show modal with task selection for text tasks."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Get tasks that don't require attachments
        tasks = [
            name
            for name, metadata in IMAGE_TASKS.items()
            if not metadata.get("requires_attachment", True)
        ]

        if not tasks:
            await interaction.followup.send("No text tasks available.", ephemeral=True)
            return

        view = TaskSelectView(tasks, requires_attachment=False, message=message)
        followup_msg = await interaction.followup.send(
            "Select a text tool:", view=view, ephemeral=True
        )
        view.followup_message = followup_msg

    async def process_image_task(
        self,
        interaction: discord.Interaction,
        task_name: str,
        message: Optional[discord.Message] = None,
        thinking_message: Optional[discord.Message] = None,
    ):
        """Process the image using the selected task."""
        task_metadata = IMAGE_TASKS.get(task_name)
        if not task_metadata:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"Task '{task_name}' is not registered.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"Task '{task_name}' is not registered.", ephemeral=True
                )
            return

        requires_attachment = task_metadata.get("requires_attachment", True)

        # Only defer if not already done (for direct calls, not select callbacks)
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if requires_attachment:
                if not message or not message.attachments:
                    await interaction.followup.send(
                        "This task requires an image attachment!", ephemeral=True
                    )
                    return

                attachment = message.attachments[0]
                if not attachment.content_type.startswith("image/"):
                    await interaction.followup.send(
                        "The attachment is not an image!", ephemeral=True
                    )
                    return

                image_bytes = await attachment.read()
                input_image = await asyncio.to_thread(
                    load_image_from_bytes, image_bytes
                )
                output_image = await asyncio.to_thread(
                    apply_image_task, task_name, input_image
                )
            else:
                if not message or not message.content:
                    await interaction.followup.send(
                        "This task requires a text message!", ephemeral=True
                    )
                    return

                output_image = await asyncio.to_thread(
                    apply_image_task, task_name, message.content
                )

            output_bytes = await asyncio.to_thread(save_image_to_bytes, output_image)

            # Reply to the original message that was right-clicked
            # The 'message' parameter is the message from the context menu interaction
            if message:
                await message.reply(
                    content=f"-# Triggered by {interaction.user.mention}",
                    file=discord.File(io.BytesIO(output_bytes), f"{task_name}.png"),
                )
            else:
                self.logger.error(f"No message provided for interaction")
                await interaction.followup.send(
                    file=discord.File(io.BytesIO(output_bytes), f"{task_name}.png")
                )

            # Delete the "thinking..." message if it exists
            if thinking_message:
                try:
                    await thinking_message.delete()
                except Exception as e:
                    self.logger.warning(f"Failed to delete thinking message: {e}")
        except Exception as e:
            self.logger.error(f"Error processing task '{task_name}': {e}")

            await interaction.followup.send(
                "Failed to process the task.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(ImageCog(bot))
