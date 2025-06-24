import io
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

from typing import Optional, Callable

# Just makes sure we decorate where the image_tasks go, cool python!
import utilities.image_tasks


class ImageCog(commands.Cog, name="ImageCog"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.register_image_tasks()

    def register_image_tasks(self):
        """
        Dynamically register context menu commands for image tasks.
        """
        from utilities.image_utils import IMAGE_TASKS  # Import the registered tasks

        for task_name in IMAGE_TASKS:
            # Create a context menu for each task
            context_menu = app_commands.ContextMenu(
                name=task_name.title(),
                callback=self.process_image_context,
            )
            # Attach the task name to the context menu
            context_menu.task_name = task_name
            self.logger.info(f"Added image task {task_name} to context menu.")

            # Add the command to the bot
            self.bot.tree.add_command(context_menu)

    async def process_image_context(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """
        Handle image processing via context menu.
        """
        task_name = interaction.command.task_name
        await self.process_image_task(interaction, task_name, message)

    async def process_image_task(
        self,
        interaction: discord.Interaction,
        task_name: str,
        message: Optional[discord.Message] = None,
    ):
        """
        Process the image using the selected task.
        """

        task_metadata = IMAGE_TASKS.get(task_name)
        if not task_metadata:
            await interaction.response.send_message(
                f"Task '{task_name}' is not registered.", ephemeral=True
            )
            return

        requires_attachment = task_metadata.get("requires_attachment", True)

        await interaction.response.defer()  # Acknowledge the interaction

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
                input_image = load_image_from_bytes(image_bytes)
                output_image = apply_image_task(task_name, input_image)
            else:
                # Handle text-based tasks
                if not message or not message.content:
                    await interaction.followup.send(
                        "This task requires a text message!", ephemeral=True
                    )
                    return

                output_image = apply_image_task(task_name, message.content)

            output_bytes = save_image_to_bytes(output_image)

            # Send the result
            await interaction.followup.send(
                file=discord.File(io.BytesIO(output_bytes), f"{task_name}.png")
            )
        except Exception as e:
            self.logger.error(f"Error processing task '{task_name}': {e}")
            await interaction.followup.send(
                "Failed to process the task.", ephemeral=True
            )
            raise e

    async def cog_unload(self):
        """
        Unload the context menus when the cog is unloaded.
        """
        for command in self.bot.tree.get_commands(type=discord.AppCommandType.message):
            if hasattr(command, "task_name"):
                self.bot.tree.remove_command(command.name)


async def setup(bot):
    await bot.add_cog(ImageCog(bot))
