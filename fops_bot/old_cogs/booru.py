# FOPS
# 2024, Fops Bot
# MIT License

import os
import re
import imp
import random
import discord
import logging
import requests
import aiohttp

from datetime import datetime
from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands, tasks

from utilities.features import (
    is_feature_enabled,
    set_feature_state,
    get_feature_data,
    get_guilds_with_feature_enabled,
    is_nsfw_enabled,
)

from saucenao_api import SauceNao
from saucenao_api.errors import SauceNaoApiError

from utilities.database import retrieve_key, store_key
from utilities.helpers import set_feature_state_helper

booru_scripts = imp.load_source(
    "booru_scripts", "fops_bot/scripts/Booru_Scripts/booru_utils.py"
)


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


class Booru(commands.Cog, name="BooruCog"):
    def __init__(self, bot):
        self.bot = bot

        # For /fav command
        self.users_with_favs = ["Wait for bot to start..."]

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

        # Configure SauceNAO
        self.sauce_api_key = os.environ.get("SAUCENAO_API_KEY", "")
        self.sauce = SauceNao(api_key=self.sauce_api_key)

    @commands.Cog.listener()
    async def on_ready(self):
        # Commands
        await self.bot.tree.sync()

        # Tasks
        self.fetch_usernames_with_favs.start()

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
        if message.author.bot or not message.attachments:
            return

        # Auto upload list is pulled from the features database
        auto_upload_list = (
            get_feature_data(message.guild.id, "booru_auto_upload")
            .get("feature_variables")
            .split(",")
        )
        if str(message.channel.id) not in auto_upload_list:
            logging.info(
                f"Not uploading image in {message.channel.id}, not in list {auto_upload_list}"
            )
            return

        # Cant process more than one at a time!
        if len(message.attachments) > 1:
            logging.info("Too many attachments")
            await message.add_reaction("🤹‍♂️")
            return

        # Must be an image
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

            # Prepare the description with user and channel information
            description = f"Uploaded by {message.author} in channel {message.channel}"

            tags = "tagme discord_archive missing_source missing_artist"

            # Check if channel name contains "vore" to add the "vore" tag
            if "vore" in message.channel.name.lower():
                tags += " vore"

            # Check if channel is memes
            if "meme" in message.channel.name.lower():
                tags += " meme"

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

                # SauceNAO integration
                logging.debug("Fetching sauce info")
                sauce_info = await self.get_sauce_info(attachment.url)
                if sauce_info["source"]:
                    confirmation_message = await message.reply(
                        f"Found author: `{sauce_info['author']}` and source: <{sauce_info['source']}> for post `{post_id}` via SauceNAO.\n"
                        f"Please react with ✅ to confirm or ❌ if incorrect!"
                    )

                    await confirmation_message.add_reaction("✅")
                    await confirmation_message.add_reaction("❌")
                else:
                    logging.warning(
                        f"SauceNAO couldn't find source for {attachment.url}"
                    )

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

    @app_commands.command(
        name="random",
        description="Grab a random image with space-separated tags!",
    )
    @app_commands.describe(tags="Like `cute canine outdoors`")
    async def random(self, interaction: discord.Interaction, tags: str):
        # Skip if not NSFW!
        if not await is_nsfw_enabled(interaction):
            return

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

        # Yeah i know the join and split tags thing is messy but go for it XD
        await interaction.response.send_message(
            f"{os.environ.get('BOORU_URL', '')}/posts/{image[0]['id']}?q={'+'.join(tags.split(' '))}"
        )

    @tasks.loop(minutes=15)
    async def fetch_usernames_with_favs(self):
        logging.info("Fetching usernames with favs...")
        self.users_with_favs = booru_scripts.fetch_usernames_with_favs(
            self.api_url, self.api_key, self.api_user
        )
        logging.info(f"Fetched {len(self.users_with_favs)} users with favs")

    # User autocompletion, useful for some things!
    async def user_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:

        return [
            app_commands.Choice(name=_name, value=_name)
            for _name in self.users_with_favs
        ][:25]
        # Discord limits to 25 choices

    @app_commands.command(
        name="fav",
        description="Grab a favorite post from a user's fav list! Use the `tags` to filter!",
    )
    @app_commands.describe(tags="Like `vulpine outdoors`")
    @app_commands.describe(
        user="If you dont see your name listed, try favoriting something and waiting 15 minutes!`"
    )
    @app_commands.autocomplete(user=user_autocomplete)
    async def fav(
        self,
        interaction: discord.Interaction,
        user: str,
        tags: str = "",
    ):
        if not await is_nsfw_enabled(interaction):
            return

        # Default tags to exclude unless explicitly included
        default_exclude = ["vore", "gore", "scat", "watersports", "loli", "shota"]

        # Check if any of the default exclude tags are included in the user's tags
        included_excludes = [tag for tag in default_exclude if tag in tags.split()]

        # Exclude the default tags that are not explicitly included
        exclude_tags = [tag for tag in default_exclude if tag not in included_excludes]

        # Prepend 'ordfav:vixi' to the tags to search within your favorites
        tags = f"ordfav:{user} {tags}"

        images = booru_scripts.fetch_images_with_tag(
            tags,
            self.api_url,
            self.api_key,
            self.api_user,
            limit=100,
            random=False,
            exclude=exclude_tags,  # Pass the exclude tags
        )

        if not images:
            await interaction.response.send_message(f"No match for `{tags}`!")
            return

        # Randomize the list of fetched images
        random.shuffle(images)

        # Pick the first random image
        selected_image = images[0]

        await interaction.response.send_message(
            f"{os.environ.get('BOORU_URL', '')}/posts/{selected_image['id']}?q={'+'.join(tags.split(' '))}"
        )

    # ==================================================
    # Feature enable/disable
    # ==================================================

    @app_commands.command(name="booru_upload")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        channel="Enable or disable automatic upload to the booru server for this channel",
        enable="Enable or disable booru upload for this channel (defaults to True)",
    )
    async def booru_upload(
        self,
        ctx: discord.Interaction,
        channel: discord.TextChannel,
        enable: bool = True,
    ):
        """
        Enables or disables booru auto-upload on a channel.
        """
        await set_feature_state_helper(
            ctx=ctx,
            feature_name="booru_auto_upload",
            enable=enable,  # Toggle feature based on the passed argument
            channels=[channel],  # Single channel at a time, but multi-channel feature
            multi_channel=True,  # Can have multiple channels
        )

    @app_commands.command(name="set_booru_maintenance")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        channel="The channel to configure for booru maintenance tasks."
    )
    async def set_booru_maintenance(
        self, ctx: discord.Interaction, channel: discord.TextChannel
    ):
        """
        Enables the booru server to post here
        """
        guild_id = ctx.guild_id

        set_feature_state(guild_id, "booru_maintenance", True, str(channel.id))

        await ctx.response.send_message(
            f"booru_maintenance enabled and channel set to {channel.mention}",
            ephemeral=True,
        )

    @app_commands.command(name="set_booru_updates")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        channel="The booru server will post regular comments and updates here"
    )
    async def set_set_booru_updates(
        self, ctx: discord.Interaction, channel: discord.TextChannel
    ):
        """
        Enables the booru server to post here
        """
        guild_id = ctx.guild_id

        set_feature_state(guild_id, "booru_updates", True, str(channel.id))

        await ctx.response.send_message(
            f"booru_updates enabled and channel set to {channel.mention}",
            ephemeral=True,
        )

    # ==================================================
    # End Feature enable/disable
    # ==================================================

    # Sauce NAO Integration stuff

    async def get_sauce_info(self, image_url: str) -> dict:
        """
        Retrieves author and source information from SauceNAO.
        """
        try:
            results = self.sauce.from_url(image_url)
            if results and results[0].similarity >= 80:
                author = results[0].author or "Unknown"
                source = results[0].urls[0] if results[0].urls else "No source found"
                return {"author": author.replace(" ", "_"), "source": source}
        except SauceNaoApiError as e:
            logging.error(f"SauceNAO error: {e}")
        return {"author": None, "source": None}

    def parse_confirmation_message(self, content):
        pattern = r"Found author: `(?P<author>.+?)` and source: <(?P<source>.+?)> for post `(?P<post_id>\d+)`"
        match = re.search(pattern, content)
        if not match:
            raise ValueError("Message content does not match the expected format.")

        return match.group("author"), match.group("source"), match.group("post_id")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """
        Handles reactions for SauceNAO confirmations.
        """

        # Ignore bot reactions
        if user.bot:
            return

        # Ensure the message reacted to was sent by the bot
        if reaction.message.author != self.bot.user:
            return

        # Get the referenced message (OP's message)
        if reaction.message.reference is None:
            logging.warning("No referenced message; cannot determine the OP.")
            return

        original_message = reaction.message.reference.resolved
        if original_message.author != user:
            logging.info(f"Ignoring reaction from non-OP user {user}.")
            return

        # Extract details from the message
        try:
            author, source, post_id = self.parse_confirmation_message(
                reaction.message.content
            )
            logging.info(
                f"Parsed confirmation message: author={author}, source={source}, post_id={post_id}"
            )
        except ValueError as e:
            logging.warning(
                f"Failed to parse confirmation message: {message.content}. Error: {e}"
            )
            return

        # Process reaction
        if reaction.emoji == "✅":
            # Append the tags and source to the post
            booru_scripts.append_source_to_post(
                post_id, source, self.api_url, self.api_key, self.api_user
            )
            booru_scripts.append_post_tags(
                post_id=post_id,
                new_tags=f"art:{author}",
                danbooru_url=self.api_url,
                api_key=self.api_key,
                username=self.api_user,
                clear_tags=["missing_artist", "missing_source"],
            )
            logging.info(f"Tags and source confirmed for {post_id}!")
        elif reaction.emoji == "❌":
            logging.warn(f"Tags and source rejected for {post_id}. :(")

        # Clean up the confirmation message
        await reaction.message.delete()


async def setup(bot):
    await bot.add_cog(Booru(bot))
