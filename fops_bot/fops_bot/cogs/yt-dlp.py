import discord
import logging
import aiohttp
import asyncio
import os
from typing import Optional
from discord.ext import commands
from urllib.parse import urlparse, urlunparse

DISCORD_FILE_SIZE_LIMIT = 8 * 1024 * 1024  # 8MB limit for Discord uploads
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
    for domain in valid_domains:
        if domain in message.content.lower():
            return domain
    return None


async def submit_yt_dlp_job(session, url):
    async with session.post(f"{YTDLP_API_URL}/submit", json={"url": url}) as resp:
        data = await resp.json()
        return data.get("job_id")


async def poll_yt_dlp_status(session, job_id, timeout=60):
    for _ in range(timeout):
        async with session.get(f"{YTDLP_API_URL}/status/{job_id}") as resp:
            data = await resp.json()
            if data.get("status") == "done":
                return True
            elif data.get("status") == "failed":
                return False
        await asyncio.sleep(1)
    return False


async def download_yt_dlp_result(session, job_id, dest_dir):
    async with session.get(f"{YTDLP_API_URL}/result/{job_id}") as resp:
        if resp.status == 200:
            dest_path = os.path.join(dest_dir, f"{job_id}.mp4")
            with open(dest_path, "wb") as f:
                while True:
                    chunk = await resp.content.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return dest_path
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

    @commands.Cog.listener("on_message")
    async def mediaListener(self, message: discord.Message):
        if message.author.bot:
            return
        domain = message_contains(message, self.valid_domains)
        if not domain:
            return
        self.logger.info(
            f'{self.valid_domains[domain]} Listener caught message "{message.content}"'
        )
        await message.add_reaction("⏳")
        twitter_domains = {"x.com", "twitter.com"}
        url = next((word for word in message.content.split() if "://" in word), None)
        if not url:
            await message.add_reaction("❌")
            return
        temp_file = f"/tmp/yt_{message.id}.dat"
        async with aiohttp.ClientSession() as session:
            try:
                job_id = await submit_yt_dlp_job(session, url)
                if not job_id:
                    await message.add_reaction("❌")
                    return
                ok = await poll_yt_dlp_status(session, job_id)
                if not ok:
                    await message.add_reaction("❌")
                    await cleanup_yt_dlp_job(session, job_id)
                    return
                result = await download_yt_dlp_result(session, job_id, temp_file)
                if result and domain not in twitter_domains:
                    try:
                        await message.reply(file=discord.File(result))
                    except discord.errors.HTTPException:
                        await message.add_reaction("⚠️")
                        await message.reply("❌ Media too large to post.")
                    finally:
                        await cleanup_yt_dlp_job(session, job_id)
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                else:
                    await message.add_reaction("❌")
                    await cleanup_yt_dlp_job(session, job_id)
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
            except Exception as e:
                self.logger.warning(f"yt-dlp API error: {e}")
                await message.add_reaction("⚠️")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        await message.clear_reaction("⏳")
        if domain in twitter_domains:
            try:
                words = message.content.split()
                for word in words:
                    if "://" in word:
                        alt_link = convert_twitter_link_to_alt(word.strip())
                        break
                else:
                    alt_link = message.content
                await message.channel.send(
                    f"Originally posted by {message.author.mention}: {alt_link}"
                )
                await message.delete()
                if os.path.exists(temp_file):
                    try:
                        await message.channel.send(file=discord.File(temp_file))
                    except discord.errors.HTTPException:
                        await message.channel.send("❌ Media too large to post.")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except discord.errors.Forbidden:
                self.logger.warning("Bot lacks permissions to delete messages.")
            except discord.errors.NotFound:
                self.logger.warning("Message was already deleted.")


async def setup(bot):
    await bot.add_cog(YTDLP(bot))
