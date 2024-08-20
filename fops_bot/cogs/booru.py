# FOPS
# 2024, Fops Bot
# MIT License

import os
import imp
import discord
import logging
import requests
import aiohttp

from datetime import datetime
from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands, tasks

from utilities.database import retrieve_key, store_key


booru_scripts = imp.load_source("booru_scripts", "fops_bot/scripts/danbooru-scripts.py")


# This is pretty cool, basically a popup UI
class TagModal(discord.ui.Modal, title="Enter Tags"):
    tags = discord.ui.TextInput(
        label="Tags",
        placeholder="Enter tags separated by spaces",
    )

    rating = discord.ui.TextInput(
        label="Rating",
        placeholder="Rating s, q or e",
    )

    def __init__(self, attachment, message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attachment = attachment
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        tags = self.tags.value
        rating = self.rating.value

        await self.attachment.save(f"./downloads/{self.attachment.filename}")

        await self.message.add_reaction("⬇")

        # Upload everything
        upload_id = booru_scripts.upload_image(
            self.api_key,
            self.api_user,
            self.api_url,
            f"./downloads/{self.attachment.filename}",
        )
        if upload_id:
            post_id = booru_scripts.create_post(
                self.api_key,
                self.api_user,
                self.api_url,
                upload_id,  # Passed from prev command
                tags,
                rating,
            )

            # if post_id != None:
            #     await self.message.add_reaction("⬆")

            #     for num in number_to_words(post_id):
            #         await self.message.add_reaction(num)

            #     await interaction.followup.send(
            #         f"Success!\nImage has been uploaded as {api_url}/posts/{post_id}",
            #         ephemeral=True,
            #     )
            # else:  # Image must have already been posted
            #     await self.message.add_reaction("white_check_mark")
            #     await interaction.followup.send(
            #         f"Looks like this image has already been tracked!",
            #         ephemeral=True,
            #     )


class Grab(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        #
        self.ctx_menu = app_commands.ContextMenu(
            name="Upload to BixiBooru",
            callback=self.grab_message_context,  # set the callback of the context menu to "grab_message_context"
        )
        self.bot.tree.add_command(self.ctx_menu)

        # Configure options and secrets
        self.api_key = os.environ.get("BOORU_KEY", "")
        self.api_user = os.environ.get("BOORU_USER", "")
        self.api_url = os.environ.get("BOORU_URL", "")
        # This one must be parsed
        self.auto_upload_list = os.environ.get("BOORU_AUTO_UPLOAD", "00,00").split(
            ", "
        )  # Todo, better way to strip whitespace

    @commands.Cog.listener()
    async def on_ready(self):
        # Tasks
        self.update_status.start()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.tree.sync()

    async def grab_message_context(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        # Check if the message contains attachments
        if not message.attachments:
            await interaction.response.send_message(
                "The message you selected dosn't contain directly embedded images! (but i will support linked images in the future.)",
                ephemeral=True,
            )
            return

        # Download the first attachment
        attachment = message.attachments[0]

        # Check if the attachment is an image
        if attachment.content_type.startswith("image/"):
            # Ensure the downloads directory exists
            os.makedirs("./downloads", exist_ok=True)
            # Show modal to collect tags
            modal = TagModal(attachment, message)
            await message.add_reaction("🤔")
            await interaction.response.send_modal(modal)
        else:
            await interaction.followup.send(
                "The attachment is not an image.", ephemeral=True
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check if the message has exactly one attachment and is an image
        if len(message.attachments) == 0:
            logging.debug(
                "No attachments!?? Vixi! DONT FORGOR: Must add discord check here!"
            )
            return

        if len(message.attachments) > 1:
            logging.info("Too many attachments")
            await message.add_reaction("🤹‍♂️")
            return

        if not message.attachments[0].content_type.startswith("image/"):
            logging.warn("Attachment is not an image?")
            await message.add_reaction("❌")
            return

        # Get attachment
        attachment = message.attachments[0]
        file_path = f"/tmp/{attachment.filename}"

        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    with open(file_path, "wb") as f:
                        f.write(await resp.read())

        # Call the get_post_id function
        post_id = booru_scripts.check_image_exists(
            file_path, self.api_url, self.api_key, self.api_user
        )

        # Check if a valid number was returned
        if post_id is not None and isinstance(post_id, int):
            post_id_str = str(post_id)

            # Check for duplicate digits
            if self.has_duplicates(post_id_str):
                logging.warn(f"Duplicated digits for post {post_id_str}")
                await message.add_reaction("🔢")
            else:
                logging.info(f"Getting digits for {post_id_str}")
                for digit in post_id_str:
                    # React with the corresponding emoji
                    await message.add_reaction(self.get_emoji(digit))
        else:
            # We get to this stage when we've looked up and confirmed that this post is unique!
            await message.add_reaction("💎")

            if str(message.channel.id) not in self.auto_upload_list:
                logging.info(
                    f"Not uploading image in {message.channel.id}, not in list {self.auto_upload_list}"
                )
                return

            # Prepare the description with user and channel information
            description = f"Uploaded by {message.author} in channel {message.channel}"

            # TODO: Move to shared func
            tags = "tagme discord_archive"
            rating = "e"

            # Upload everything
            upload_id = booru_scripts.upload_image(
                self.api_key,
                self.api_user,
                self.api_url,
                file_path,  # <- Same path as earlier
            )
            if upload_id:
                post_id = booru_scripts.create_post(
                    self.api_key,
                    self.api_user,
                    self.api_url,
                    upload_id,  # Passed from prev command
                    tags,
                    rating,
                    description=description,  # Pass the description here
                )

                post_id_str = str(post_id)

                # Check for duplicate digits
                if self.has_duplicates(post_id_str):
                    logging.warn(f"Duplicated digits for post {post_id_str}")
                    await message.add_reaction("🔢")
                else:
                    for digit in post_id_str:
                        # React with the corresponding emoji
                        await message.add_reaction(self.get_emoji(digit))
            # TODO: Move to shared func

        # Increment image count
        ic = retrieve_key("image_count", 1)
        store_key("image_count", int(ic) + 1)

        # Clean up the download
        os.remove(file_path)

    def get_emoji(self, digit):
        # Map digit to corresponding emoji
        emoji_map = {
            "0": "0️⃣",
            "1": "1️⃣",
            "2": "2️⃣",
            "3": "3️⃣",
            "4": "4️⃣",
            "5": "5️⃣",
            "6": "6️⃣",
            "7": "7️⃣",
            "8": "8️⃣",
            "9": "9️⃣",
        }

        try:
            return emoji_map[digit]
        except KeyError:
            logging.warn(f"Couldn't decode key {digit}")
            return "❓"

    def has_duplicates(self, s):
        # Check for duplicate characters in the string
        return len(s) != len(set(s))

    @tasks.loop(minutes=1)
    async def update_status(self):
        current_minute = datetime.now().minute

        if current_minute % 2 == 0:
            await self.bot.change_presence(
                activity=discord.Game(
                    name=f"images scanned: {retrieve_key('image_count', 1)}"
                )
            )
        else:
            await self.bot.change_presence(
                activity=discord.Game(name=f"Running Version {self.bot.version}")
            )

    @update_status.before_loop
    async def before_update_status(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="random",
        description="Grab a random image with space-separated tags!",
    )
    @app_commands.describe(tags="Like `cute canine outdoors`")
    async def random(self, interaction: discord.Interaction, tags: str):
        # Default tags to exclude unless explicitly included
        default_exclude = ["vore", "gore", "scat", "watersports", "loli", "shota"]

        # Check if any of the default exclude tags are included in the user's tags
        included_excludes = [tag for tag in default_exclude if tag in tags.split()]

        # Exclude the default tags that are not explicitly included
        exclude_tags = [tag for tag in default_exclude if tag not in included_excludes]

        image = booru_scripts.fetch_images_with_tag(
            tags,
            self.api_url,
            self.api_key,
            self.api_user,
            limit=1,
            random=True,
            exclude=exclude_tags,  # Pass the exclude tags
        )

        if not image:
            await interaction.response.send_message(f"No match for `{tags}`!")
            return

        await interaction.response.send_message(
            f"{os.environ.get('BOORU_URL', '')}/posts/{image[0]['id']}"
        )


async def setup(bot):
    await bot.add_cog(Grab(bot))

    # for cmd in bot.tree.get_commands():
    #     print(f"Command available: {cmd.name}")
