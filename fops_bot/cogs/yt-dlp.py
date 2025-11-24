import os
import time
import uuid
import json
import discord
import logging
import asyncio
import tempfile

from typing import Optional
from discord.ext import commands
from urllib.parse import urlparse, urlunparse

from cogs.guild_cog import get_guild
from utilities.influx_metrics import send_metric
from utilities.redis_client import redis_client
from utilities.guild_log import (
    info as guild_log_info,
    warning as guild_log_warning,
    error as guild_log_error,
)


def convert_twitter_link_to_alt(
    original_url: str, alt_domain: str = "fxtwitter.com"
) -> str:
    try:
        parsed = urlparse(original_url)
        if parsed.netloc in {"x.com", "twitter.com"}:
            new_url = parsed._replace(netloc=alt_domain)
            return urlunparse(new_url)
    except Exception as e:
        logging.warning(f"URL parse error: {e}")
    return original_url


def message_contains(message: discord.Message, valid_domains: dict) -> Optional[str]:
    """Check if message contains a URL with one of the valid domains."""
    content_lower = message.content.lower()

    # Look for URLs in the message
    for word in content_lower.split():
        if "://" not in word:
            continue

        # Parse the URL to get the domain
        try:
            parsed = urlparse(word)
            domain = parsed.netloc.lower()

            # Check if this domain matches any of our valid domains
            for valid_domain in valid_domains:
                if domain == valid_domain or domain.endswith("." + valid_domain):
                    return valid_domain
        except Exception:
            continue

    return None


async def submit_yt_dlp_job(url):
    """Submit a job to yt-dlp service via Redis"""
    job_id = str(uuid.uuid4())
    job_data = {"job_id": job_id, "url": url}

    if redis_client.publish_job("ytdlp:jobs", job_data):
        return job_id
    return None


async def wait_for_job_completion(job_id, timeout=300):
    """Wait for job completion via Redis pub/sub"""

    # Use asyncio to run the blocking Redis pubsub in a thread
    loop = asyncio.get_event_loop()

    def _wait_for_message():
        pubsub = redis_client.subscribe_to_channel("ytdlp:status")
        if not pubsub:
            logging.error(f"Failed to subscribe to ytdlp:status channel")
            return None

        try:
            start_time = time.time()

            for message in pubsub.listen():
                # Check timeout
                if time.time() - start_time > timeout:
                    logging.warning(f"Job {job_id} timed out after {timeout}s")
                    return None

                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        if data.get("job_id") == job_id:
                            status = data.get("status")
                            if status == "done":
                                logging.info(f"Job {job_id} completed successfully")
                                return True
                            elif status == "failed":
                                logging.warning(f"Job {job_id} failed")
                                return False
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logging.error(f"Error waiting for job completion: {e}")
            return None
        finally:
            pubsub.close()

        return None  # Timed out

    # Run the blocking Redis operation in a thread pool
    result = await loop.run_in_executor(None, _wait_for_message)
    return result


async def download_yt_dlp_result(job_id, temp_file_path):
    """Download result file from yt-dlp service"""
    status_data = redis_client.get_job_status(job_id)
    if not status_data:
        logging.warning(f"Job {job_id}: No status data found in Redis")
        return None

    status = status_data.get("status")
    if status != "done":
        logging.warning(f"Job {job_id}: Status is '{status}', expected 'done'")
        return None

    result_path = status_data.get("result_path")
    if not result_path:
        logging.warning(
            f"Job {job_id}: No result_path in status data. Status data: {status_data}"
        )
        return None

    if not os.path.exists(result_path):
        logging.warning(f"Job {job_id}: Result file does not exist at {result_path}")
        # Check if directory exists
        result_dir = os.path.dirname(result_path)
        if os.path.exists(result_dir):
            logging.info(
                f"Job {job_id}: Directory exists, listing contents: {os.listdir(result_dir)}"
            )
        else:
            logging.warning(f"Job {job_id}: Directory does not exist: {result_dir}")
        return None

    # Copy file to temp location
    import shutil

    try:
        shutil.copy2(result_path, temp_file_path)
        logging.info(
            f"Job {job_id}: Successfully copied {result_path} to {temp_file_path}"
        )
        return temp_file_path
    except Exception as e:
        logging.error(f"Job {job_id}: Failed to copy file: {e}")
        return None


async def cleanup_yt_dlp_job(job_id):
    """Clean up job resources"""
    redis_client.delete_job_status(job_id)


class YTDLP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.valid_domains = {
            "instagram.com": "Instagram",
            "instagramez.com": "Instagram",
            "facebook.com": "Facebook",
            "x.com": "Twitter",
            "fixupx.com": "Twitter",
            "fxtwitter.com": "Twitter",
            "twitter.com": "Twitter",
            "tiktok.com": "TikTok",
            "youtube.com": "YouTube",
            "youtu.be": "YouTube",
            "vxtwitter.com": "Twitter",
            "fxbsky.app": "Bluesky",
            "bsky.app": "Bluesky",
        }

    async def send_error_to_admin(self, message: discord.Message, error_msg: str):
        """Send error message to guild's admin channel if configured."""
        if not message.guild:
            return

        guild_settings = get_guild(message.guild.id)
        if not guild_settings:
            return

        admin_channel_id = guild_settings.admin_channel()
        if not admin_channel_id:
            return

        try:
            channel = self.bot.get_channel(admin_channel_id)
            if channel:
                # Create a jump link to the original message
                message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                await channel.send(
                    f"⚠️ **yt-dlp Error**\n{error_msg}\n[Jump to message]({message_link})"
                )
        except Exception as e:
            guild_log_error(
                self.logger,
                message.guild.id if message.guild else None,
                f"Failed to send error to admin channel: {e}",
            )

    @commands.Cog.listener("on_message")
    async def mediaListener(self, message: discord.Message):
        # Don't listen to bots
        if message.author.bot:
            return

        # Only work in guilds (not DMs)
        if not message.guild:
            return

        # Check if guild has DLP enabled
        guild_settings = get_guild(message.guild.id)
        if not guild_settings or not guild_settings.dlp():
            return

        guild_id = message.guild.id

        # Check if the message contains a domain we can convert
        domain = message_contains(message, self.valid_domains)
        if not domain:
            return

        # We got one!
        guild_log_info(
            self.logger,
            guild_id,
            f'{self.valid_domains[domain]} Listener caught message "{message.content}" in {message.guild.name}',
        )

        # Be explicit with twitter domains
        twitter_domains = {"x.com", "twitter.com"}

        # Walk and find the URL
        url = next((word for word in message.content.split() if "://" in word), None)
        if not url:
            guild_log_warning(
                self.logger,
                guild_id,
                "No URL found in message with valid domain",
            )
            return

        # Try to download the video
        temp_file = None
        job_id = None
        result = None
        try:
            job_id = await submit_yt_dlp_job(url)
            if not job_id:
                guild_log_warning(
                    self.logger, guild_id, f"Failed to submit job for {url}"
                )
                await self.send_error_to_admin(message, "Failed to submit download job")
                return

            # Track job submission in InfluxDB
            send_metric("ytdlp_job_submitted", message.guild.id, message.guild.name)

            ok = await wait_for_job_completion(job_id)

            if ok is True:
                # Download to a temp file for Discord upload
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    temp_file = tmp.name

                result = await download_yt_dlp_result(job_id, temp_file)
                await cleanup_yt_dlp_job(job_id)

            elif ok is False:
                guild_log_warning(self.logger, guild_id, f"Download failed for {url}")
                await cleanup_yt_dlp_job(job_id)
                send_metric("ytdlp_job_failed", message.guild.id, message.guild.name)

            else:  # Timed out
                guild_log_warning(
                    self.logger, guild_id, f"Download timed out for {url}"
                )
                if job_id:
                    await cleanup_yt_dlp_job(job_id)
                send_metric("ytdlp_job_timeout", message.guild.id, message.guild.name)

            # Always post video if it exists
            if result:
                try:
                    content = f"-# Visit [snowsune.net/fops](https://snowsune.net/fops/redirect) to edit bot settings!"
                    if (
                        domain in twitter_domains
                        and guild_settings
                        and guild_settings.obfuscate_twitter()
                    ):
                        wrapper_domain = guild_settings.twitter_wrapper_domain()
                        twt_url = (
                            f"({convert_twitter_link_to_alt(url, wrapper_domain)})"
                        )

                        # The content if obfuscated
                        content = f"Originally posted by {message.author.mention} {twt_url}\n{content}"
                    else:
                        # Just the normal content
                        content = f"{content}"

                    # The actual posting
                    await message.reply(content=content, file=discord.File(result))

                    guild_log_info(
                        self.logger, guild_id, f"Successfully posted video for {url}"
                    )
                    send_metric("video_downloads", message.guild.id, message.guild.name)
                    send_metric(
                        "ytdlp_job_completed", message.guild.id, message.guild.name
                    )

                    # If Twitter, delete original message
                    if (
                        domain in twitter_domains
                        and guild_settings
                        and guild_settings.obfuscate_twitter()
                    ):
                        try:
                            await message.delete()
                        except (discord.errors.Forbidden, discord.errors.NotFound):
                            pass
                except discord.errors.HTTPException as e:
                    guild_log_warning(
                        self.logger, guild_id, f"Media too large to post: {e}"
                    )
                    await self.send_error_to_admin(
                        message, "Media file too large to post"
                    )

        except Exception as e:
            guild_log_warning(self.logger, guild_id, f"yt-dlp Redis error: {e}")
            if job_id:
                await cleanup_yt_dlp_job(job_id)

            # Track job error in InfluxDB
            send_metric("ytdlp_job_error", message.guild.id, message.guild.name)
            # Only send to admin if it's not a connection error (service down)
            if "Redis connection" not in str(e):
                await self.send_error_to_admin(message, f"Unexpected error: {str(e)}")

        finally:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)

        # Twitter obfuscation: only if no video was posted
        if (
            not result
            and domain in twitter_domains
            and guild_settings
            and guild_settings.obfuscate_twitter()
        ):
            try:
                wrapper_domain = guild_settings.twitter_wrapper_domain()
                alt_link = convert_twitter_link_to_alt(url, wrapper_domain)
                preserved_text = message.content.replace(url, "").strip()
                formatted_text = preserved_text or ""
                intro_line = f"Originally posted by {message.author.mention}"
                if formatted_text:
                    intro_line += f"\n>>> {formatted_text}"

                await message.channel.send(f"{alt_link}\n{intro_line}")
                await message.delete()
            except (discord.errors.Forbidden, discord.errors.NotFound):
                pass


async def setup(bot):
    await bot.add_cog(YTDLP(bot))
