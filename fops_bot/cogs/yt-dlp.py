import discord
import logging
import aiohttp
import asyncio
import os
import tempfile
from typing import Optional
from discord.ext import commands
from urllib.parse import urlparse, urlunparse

from cogs.guild_cog import get_guild

YTDLP_API_URL = os.environ.get("YTDLP_API_URL", "http://yt-dlp:5000")


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


async def submit_yt_dlp_job(session, url):
    async with session.post(f"{YTDLP_API_URL}/submit", json={"url": url}) as resp:
        data = await resp.json()
        return data.get("job_id")


async def poll_yt_dlp_status(session, job_id, timeout=300):
    # timeout in seconds (default 5 minutes)
    for _ in range(timeout):
        async with session.get(f"{YTDLP_API_URL}/status/{job_id}") as resp:
            data = await resp.json()
            if data.get("status") == "done":
                return True
            elif data.get("status") == "failed":
                return False
        await asyncio.sleep(1)
    return None  # Timed out


async def download_yt_dlp_result(session, job_id, temp_file_path):
    async with session.get(f"{YTDLP_API_URL}/result/{job_id}") as resp:
        if resp.status == 200:
            with open(temp_file_path, "wb") as f:
                while True:
                    chunk = await resp.content.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return temp_file_path
        return None


async def cleanup_yt_dlp_job(session, job_id):
    await session.post(f"{YTDLP_API_URL}/cleanup/{job_id}")


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
            self.logger.error(f"Failed to send error to admin channel: {e}")

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

        # Check if the message contains a domain we can convert
        domain = message_contains(message, self.valid_domains)
        if not domain:
            return

        # We got one!
        self.logger.info(
            f'{self.valid_domains[domain]} Listener caught message "{message.content}" in {message.guild.name}'
        )

        # Be explicit with twitter domains
        twitter_domains = {"x.com", "twitter.com"}

        # Walk and find the URL
        url = next((word for word in message.content.split() if "://" in word), None)
        if not url:
            self.logger.warning("No URL found in message with valid domain")
            return

        # Try to download the video
        async with aiohttp.ClientSession() as session:
            temp_file = None
            job_id = None
            try:
                job_id = await submit_yt_dlp_job(session, url)
                if not job_id:
                    self.logger.warning(f"Failed to submit job for {url}")
                    await self.send_error_to_admin(
                        message, "Failed to submit download job"
                    )
                    return

                ok = await poll_yt_dlp_status(session, job_id)

                if ok is True:
                    # Download to a temp file for Discord upload
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".mp4"
                    ) as tmp:
                        temp_file = tmp.name

                    result = await download_yt_dlp_result(session, job_id, temp_file)
                    await cleanup_yt_dlp_job(session, job_id)

                    if result and domain not in twitter_domains:
                        # Successfully downloaded - reply with the video
                        try:
                            await message.reply(
                                content=f"-# Visit [snowsune.net/fops](https://snowsune.net/fops/redirect) to edit bot settings!",
                                file=discord.File(result),
                            )
                            self.logger.info(f"Successfully posted video for {url}")
                        except discord.errors.HTTPException as e:
                            self.logger.warning(f"Media too large to post: {e}")
                            await self.send_error_to_admin(
                                message, "Media file too large to post"
                            )
                    else:
                        # No result or Twitter (likely just an image post) - be silent
                        self.logger.warning(f"No video result for {url}")

                elif ok is False:
                    # Download failed
                    self.logger.warning(f"Download failed for {url}")
                    await cleanup_yt_dlp_job(session, job_id)
                    # await self.send_error_to_admin(
                    #     message, "Error downloading video from post"
                    # )

                else:  # Timed out
                    self.logger.warning(f"Download timed out for {url}")
                    if job_id:
                        await cleanup_yt_dlp_job(session, job_id)
                    await self.send_error_to_admin(message, "Download timed out")

            except Exception as e:
                self.logger.warning(f"yt-dlp API error: {e}")
                if job_id:
                    await cleanup_yt_dlp_job(session, job_id)
                # Only send to admin if it's not a connection error (service down)
                if "Cannot connect" not in str(e):
                    await self.send_error_to_admin(
                        message, f"Unexpected error: {str(e)}"
                    )

            finally:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)

        # Twitter link obfuscation (fxtwitter.com reposting)
        if (
            domain in twitter_domains
            and guild_settings
            and guild_settings.obfuscate_twitter()
        ):
            try:
                # Find the URL in the message and convert it
                words = message.content.split()
                for word in words:
                    if "://" in word:
                        alt_link = convert_twitter_link_to_alt(word.strip())
                        break
                else:
                    alt_link = message.content

                # Repost with obfuscated link
                await message.channel.send(
                    f"Originally posted by {message.author.mention}: {alt_link}"
                )
                await message.delete()
            except discord.errors.Forbidden:
                self.logger.warning(
                    f"Bot lacks permissions to delete messages in {message.guild.name}."
                )
            except discord.errors.NotFound:
                self.logger.warning(
                    f"Message was already deleted in {message.guild.name}."
                )


async def setup(bot):
    await bot.add_cog(YTDLP(bot))
