import uuid
import time
import os
import shutil
import logging
import subprocess
import json
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from yt_dlp_logic import run_yt_dlp, compress_file_if_needed, cleanup_files
from threading import Thread
from utilities.redis_client import redis_client

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s"
)

jobs = {}
shared_output_root = "/tmp/yt_dlp_output"
os.makedirs(shared_output_root, exist_ok=True)

MAX_JOB_SECONDS = 600
MAX_WORKERS = 4
YTDLP_JOB_CHANNEL = "ytdlp:jobs"
YTDLP_STATUS_CHANNEL = "ytdlp:status"
shutdown_flag = False


def yt_dlp_worker(job_id, url):
    job_output_dir = os.path.join(shared_output_root, job_id)
    os.makedirs(job_output_dir, exist_ok=True)
    logging.info(f"[Worker] Starting job {job_id} for URL: {url}")

    # Update status in Redis
    status_data = {
        "status": "running",
        "started_at": time.time(),
        "url": url,
        "result_path": None,
        "original_path": None,
        "error": None,
    }
    redis_client.set_job_status(job_id, status_data)
    redis_client.publish_job(
        YTDLP_STATUS_CHANNEL, {"job_id": job_id, "status": "running"}
    )

    try:
        file_path = run_yt_dlp(url, job_output_dir, job_id, timeout=MAX_JOB_SECONDS)
        if not file_path:
            status_data["status"] = "failed"
            status_data["error"] = "yt-dlp failed or no file"
            redis_client.set_job_status(job_id, status_data)
            redis_client.publish_job(
                YTDLP_STATUS_CHANNEL, {"job_id": job_id, "status": "failed"}
            )
            logging.error(f"[Worker] Job {job_id} failed: yt-dlp failed or no file")
            shutil.rmtree(job_output_dir, ignore_errors=True)

            return status_data

        status_data["original_path"] = file_path
        logging.info(f"[Worker] Job {job_id} downloaded file: {file_path}")
        result_path = compress_file_if_needed(file_path, timeout=MAX_JOB_SECONDS)
        status_data["result_path"] = result_path

        if result_path:
            status_data["status"] = "done"
            status_data["finished_at"] = time.time()
            redis_client.set_job_status(job_id, status_data)
            redis_client.publish_job(
                YTDLP_STATUS_CHANNEL, {"job_id": job_id, "status": "done"}
            )
            logging.info(f"[Worker] Job {job_id} completed. Result file: {result_path}")
        else:
            status_data["status"] = "failed"
            status_data["error"] = "Compression failed or file too large"
            status_data["finished_at"] = time.time()
            redis_client.set_job_status(job_id, status_data)
            redis_client.publish_job(
                YTDLP_STATUS_CHANNEL, {"job_id": job_id, "status": "failed"}
            )
            logging.error(
                f"[Worker] Job {job_id} failed: Compression failed or file too large"
            )

        # Clean up all files in the job directory except the result file
        for f in os.listdir(job_output_dir):
            fpath = os.path.join(job_output_dir, f)
            if fpath != result_path:
                os.remove(fpath)
                logging.info(f"[Worker] Job {job_id} cleaned up file: {fpath}")

    except Exception as e:
        status_data["status"] = "failed"
        status_data["error"] = str(e)
        status_data["finished_at"] = time.time()
        redis_client.set_job_status(job_id, status_data)
        redis_client.publish_job(
            YTDLP_STATUS_CHANNEL, {"job_id": job_id, "status": "failed"}
        )
        logging.exception(f"[Worker] Job {job_id} encountered an exception:")
        shutil.rmtree(job_output_dir, ignore_errors=True)

    return status_data


def redis_job_processor():
    """Process jobs from Redis queue"""
    pubsub = redis_client.subscribe_to_channel(YTDLP_JOB_CHANNEL)
    if not pubsub:
        logging.error("Failed to subscribe to Redis job channel")
        return

    logging.info("Started Redis job processor")
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    try:
        for message in pubsub.listen():
            if shutdown_flag:
                break

            if message["type"] == "message":
                try:
                    job_data = json.loads(message["data"])
                    job_id = job_data.get("job_id")
                    url = job_data.get("url")

                    if not job_id or not url:
                        logging.error(f"Invalid job data received: {job_data}")
                        continue

                    logging.info(f"[Redis] Processing job {job_id} for URL: {url}")
                    executor.submit(yt_dlp_worker, job_id, url)

                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse job message: {e}")
                except Exception as e:
                    logging.error(f"Error processing job: {e}")

    except Exception as e:
        logging.error(f"Redis job processor error: {e}")
    finally:
        pubsub.close()
        executor.shutdown()
        logging.info("Redis job processor stopped")


def update_health_status():
    """Update service health status in Redis"""
    while not shutdown_flag:
        try:
            ytdlp_version = (
                subprocess.check_output(["yt-dlp", "--version"]).decode().strip()
            )
            health_data = {
                "status": "ok",
                "yt-dlp_version": ytdlp_version,
                "jobs": len(jobs),
                "timestamp": time.time(),
            }
            redis_client.set_service_health("ytdlp", health_data)
            time.sleep(30)
        except Exception as e:
            logging.error(f"Health status update error: {e}")
            time.sleep(30)


def signal_handler(signum, frame):
    global shutdown_flag
    logging.info("Received shutdown signal, stopping gracefully...")
    shutdown_flag = True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        redis_client.client.ping()
        logging.info("Connected to Redis successfully")
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        sys.exit(1)

    Thread(target=redis_job_processor, daemon=True).start()
    Thread(target=update_health_status, daemon=True).start()

    logging.info("yt-dlp service started with Redis support")

    # Keep main thread alive
    try:
        while not shutdown_flag:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
