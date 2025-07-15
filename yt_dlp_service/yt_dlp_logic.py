import os
import shutil
import subprocess
import logging
from urllib.parse import urlparse, urlunparse

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


def run_yt_dlp(url: str, output_dir: str, job_id: str) -> str | None:
    """Run yt-dlp and return the output file path, or None on failure."""
    if os.path.isdir(output_dir):
        try:
            os.rmdir(output_dir)
        except OSError:
            shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, f"{job_id}.%(ext)s")
    try:
        result = subprocess.run(
            ["yt-dlp", url, "-o", out_template], capture_output=True, text=True
        )
        if result.returncode != 0:
            logging.error(f"yt-dlp failed: {result.stderr}")
            return None
        files = os.listdir(output_dir)
        if not files:
            logging.error("No files found in output directory")
            return None
        return os.path.join(output_dir, files[0])
    except Exception as e:
        logging.error(f"yt-dlp exception: {e}")
        return None


def compress_file_if_needed(
    file_path: str, size_limit: int = DISCORD_FILE_SIZE_LIMIT
) -> str | None:
    """Compress the file using ffmpeg if it's too large. Returns new file path or original if not needed."""
    if os.path.getsize(file_path) <= size_limit:
        return file_path
    logging.info(f"File size too large, compressing {file_path}")
    base, ext = os.path.splitext(file_path)
    compressed_file = f"{base}_compressed{ext}"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                file_path,
                "-vf",
                "scale=iw/4:ih/4",
                "-b:v",
                "500k",
                "-maxrate",
                "500k",
                "-bufsize",
                "1000k",
                "-r",
                "24",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                compressed_file,
            ],
            check=True,
        )
        if os.path.getsize(compressed_file) <= size_limit:
            return compressed_file
        else:
            logging.error("Compressed file is still too large.")
            return None
    except subprocess.CalledProcessError as e:
        logging.error(f"ffmpeg compression failed: {e}")
        return None


def cleanup_files(*file_paths):
    for path in file_paths:
        if path and os.path.isfile(path):
            os.remove(path)
