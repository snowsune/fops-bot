import discord
import logging
import subprocess
import os
import shutil

from typing import Optional
from discord.ext import commands

DISCORD_FILE_SIZE_LIMIT = 8 * 1024 * 1024  # 8MB limit for Discord uploads


class VideoExtractor:
    def __init__(self, _content):
        self.message_content = _content
        self.output_dir = "/tmp/ytdlp_output"
        self.compressed_file = None

    def __enter__(self) -> Optional[str]:
        logging.info(f"Video Extractor Processing {self.message_content}")

        # Extract the URL
        url = next(
            (word for word in self.message_content.split() if "://" in word), None
        )

        if not url:
            logging.warning(
                f'Found link in message "{self.message_content}" but could not extract url'
            )
            return None  # No valid URL found

        # Create output directory
        if os.path.isdir(self.output_dir):
            try:
                os.rmdir(self.output_dir)
            except OSError:
                logging.warn("Had to remove leftover files..")
                shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir)

        # Execute yt-dlp with the URL
        try:
            command = [
                "yt-dlp",
                url,
                "-o",
                os.path.join(self.output_dir, "%(title)s.%(ext)s"),
            ]
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"yt-dlp failed: {e}")
            return None

        # Find the video or image file it produced
        files = os.listdir(self.output_dir)
        if not files:
            logging.error("No files found in output directory")
            return None

        self.file_path = os.path.join(self.output_dir, files[0])

        # If we succeed, return this object
        if os.path.isfile(self.file_path):
            return self
        return None

    def path(self):
        return self.file_path

    def compress_file(self) -> Optional[str]:
        """
        Compress the file using ffmpeg if it's too large.
        """
        # Compress only if the file exists and is larger than the Discord limit
        if os.path.getsize(self.file_path) > DISCORD_FILE_SIZE_LIMIT:
            logging.info(f"File size too large, compressing {self.file_path}")

            # Define the path for the compressed file
            self.compressed_file = self.file_path.replace(".", "_compressed.")
            try:
                # Run ffmpeg to compress the video more aggressively
                subprocess.run(
                    [
                        "ffmpeg",
                        "-i",
                        self.file_path,
                        "-vf",
                        "scale=iw/4:ih/4",  # Resize by quarter
                        "-b:v",
                        "500k",  # Set video bitrate to 500kbps
                        "-maxrate",
                        "500k",  # Cap max bitrate
                        "-bufsize",
                        "1000k",  # Buffer size for bitrate control
                        "-r",
                        "24",  # Reduce frame rate to 24 fps
                        "-c:a",
                        "aac",  # Encode audio to AAC for smaller size
                        "-b:a",
                        "128k",  # Set audio bitrate to 128kbps
                        self.compressed_file,
                    ],
                    check=True,
                )

                if os.path.getsize(self.compressed_file) <= DISCORD_FILE_SIZE_LIMIT:
                    return self.compressed_file
                else:
                    logging.error("Compressed file is still too large.")
                    return None
            except subprocess.CalledProcessError as e:
                logging.error(f"ffmpeg compression failed: {e}")
                return None
        return self.file_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.isfile(self.file_path):
            os.remove(self.file_path)
        if self.compressed_file and os.path.isfile(self.compressed_file):
            os.remove(self.compressed_file)
        os.rmdir(self.output_dir)


def message_contains(message: discord.Message, valid_domains: dict) -> Optional[str]:
    """
    Checks if the message contains a URL from a valid domain.
    Returns the domain if found, otherwise None.
    """
    for domain in valid_domains:
        if domain in message.content.lower():
            return domain
    return None


class YTDLP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.valid_domains = {
            "instagram.com": "Instagram",
            "instagramez.com": "Instagram",
            "facebook.com": "Facebook",
            "x.com": "Twitter",
            "fixupx.com": "Twitter",
            "fxtwitter.com": "Twitter",
            "tiktok.com": "TikTok",
            "youtube.com": "YouTube",
            "youtu.be": "YouTube",
            "vxtwitter.com": "Twitter",
        }

    @commands.Cog.listener("on_message")
    async def mediaListener(self, message: discord.Message):
        """
        Listener for messages containing media URLs. Handles various domains like Instagram, Facebook, Twitter.
        """

        # Ignore if the author is a bot
        if message.author.bot:
            return

        # Check if the message contains a valid domain
        domain = message_contains(message, self.valid_domains)
        if not domain:
            return

        logging.info(
            f'{self.valid_domains[domain]} Listener caught message "{message.content}"'
        )

        # React with an hourglass to indicate processing
        await message.add_reaction("⏳")

        # Use the VideoExtractor to download the media
        with VideoExtractor(message.content) as video:
            if video is not None:
                video_path = video.path()
                if video_path is not None:
                    try:
                        await message.reply(file=discord.File(video_path))
                    except discord.errors.HTTPException:
                        await message.add_reaction("⚠️")
                        compressed_path = video.compress_file()
                        if compressed_path:
                            await message.reply(
                                "(File was compressed)",
                                file=discord.File(compressed_path),
                            )
                        else:
                            await message.add_reaction("❌")
                else:
                    await message.add_reaction("❌")
            else:
                await message.add_reaction("⚠️")  # Warn about failure

        # Remove the hourglass reaction after processing
        await message.clear_reaction("⏳")


async def setup(bot):
    await bot.add_cog(YTDLP(bot))
