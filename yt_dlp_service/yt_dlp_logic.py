import os
import shutil
import subprocess
import logging
from urllib.parse import urlparse, urlunparse
from typing import Optional

DISCORD_FILE_SIZE_LIMIT = 8 * 1024 * 1024  # 8MB


def extract_url_from_text(text: str):
    """Extract the first URL from a string."""
    return next((word for word in text.split() if "://" in word), None)


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


def run_yt_dlp(
    url: str, output_dir: str, job_id: str, timeout: Optional[int] = None
) -> str | None:
    """Run yt-dlp and return the output mp4 file path, or None on failure."""
    if os.path.isdir(output_dir):
        try:
            os.rmdir(output_dir)
        except OSError:
            shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, f"{job_id}.mp4")
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                url,
                "-o",
                out_template,
                "--merge-output-format",
                "mp4",  # For best compatibilty.
                "-f",
                "mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logging.error(f"yt-dlp failed: {result.stderr}")
            return None
        # Check for the mp4 file
        if os.path.isfile(out_template):
            return out_template
        else:
            logging.error("yt-dlp did not produce an mp4 file")
            return None
    except subprocess.TimeoutExpired:
        logging.error(f"yt-dlp timed out after {timeout} seconds")
        return None
    except Exception as e:
        logging.error(f"yt-dlp exception: {e}")
        return None


def compress_file_if_needed(
    file_path: str,
    size_limit: int = DISCORD_FILE_SIZE_LIMIT,
    timeout: Optional[int] = None,
) -> str | None:
    """Compress the file using ffmpeg if it's too large. Returns new file path or original if not needed."""
    original_size = os.path.getsize(file_path)
    if original_size <= size_limit:
        return file_path

    logging.info(
        f"File size too large ({original_size:,} bytes), compressing {file_path}"
    )
    base, ext = os.path.splitext(file_path)
    compressed_file = f"{base}_compressed{ext}"

    # Calculate compression ratio needed
    compression_ratio = original_size / size_limit
    logging.info(
        f"Need compression ratio of {compression_ratio:.2f}x to fit {size_limit:,} bytes"
    )

    # Calculate optimal settings based on compression ratio
    if compression_ratio <= 1.5:
        # Light compression - just reduce bitrate slightly
        scale_factor = 1.0
        video_bitrate = "800k"
        audio_bitrate = "128k"
        framerate = "30"
    elif compression_ratio <= 2.0:
        # Medium compression - reduce resolution slightly
        scale_factor = 0.8
        video_bitrate = "600k"
        audio_bitrate = "128k"
        framerate = "30"
    elif compression_ratio <= 3.0:
        # Moderate compression
        scale_factor = 0.6
        video_bitrate = "500k"
        audio_bitrate = "128k"
        framerate = "24"
    elif compression_ratio <= 4.0:
        # Heavy compression
        scale_factor = 0.5
        video_bitrate = "400k"
        audio_bitrate = "96k"
        framerate = "24"
    elif compression_ratio <= 6.0:
        # Very heavy compression
        scale_factor = 0.4
        video_bitrate = "300k"
        audio_bitrate = "96k"
        framerate = "20"
    elif compression_ratio <= 8.0:
        # Extreme compression
        scale_factor = 0.3
        video_bitrate = "250k"
        audio_bitrate = "64k"
        framerate = "18"
    else:
        # Maximum compression for very large files
        scale_factor = 0.25
        video_bitrate = "200k"
        audio_bitrate = "64k"
        framerate = "15"

    # Build scale filter
    if scale_factor < 1.0:
        scale_filter = f"scale=iw*{scale_factor}:ih*{scale_factor}"
    else:
        scale_filter = "scale=iw:ih"  # No scaling

    logging.info(
        f"Using compression: {scale_filter} @ {video_bitrate} video, {audio_bitrate} audio, {framerate}fps"
    )

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                file_path,
                "-vf",
                scale_filter,
                "-b:v",
                video_bitrate,
                "-maxrate",
                video_bitrate,
                "-bufsize",
                f"{int(video_bitrate[:-1]) * 2}k",  # Buffer size = 2x bitrate
                "-r",
                framerate,
                "-c:a",
                "aac",
                "-b:a",
                audio_bitrate,
                "-y",  # Overwrite output file
                compressed_file,
            ],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        compressed_size = os.path.getsize(compressed_file)
        logging.info(
            f"Compression result: {original_size:,} → {compressed_size:,} bytes ({compressed_size/size_limit:.2f}x limit)"
        )

        if compressed_size <= size_limit:
            return compressed_file
        else:
            logging.error(
                f"Compressed file still too large: {compressed_size:,} bytes (limit: {size_limit:,})"
            )
            return None

    except subprocess.TimeoutExpired:
        logging.error(f"ffmpeg compression timed out after {timeout} seconds")
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"ffmpeg compression failed: {e}")
        return None


def cleanup_files(*file_paths):
    for path in file_paths:
        if path and os.path.isfile(path):
            os.remove(path)
