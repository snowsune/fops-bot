import uuid
import time
import os
import shutil
import logging
import subprocess
from flask import Flask, jsonify, request, send_file
from concurrent.futures import ThreadPoolExecutor, as_completed
from yt_dlp_logic import run_yt_dlp, compress_file_if_needed, cleanup_files

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s"
)

app = Flask(__name__)

jobs = {}
jobs_lock = (
    None  # Not needed for ThreadPoolExecutor, but keep for status/result/cleanup
)
shared_output_root = "/tmp/yt_dlp_output"
os.makedirs(shared_output_root, exist_ok=True)

MAX_JOB_SECONDS = 600  # 10 minutes per job
MAX_WORKERS = 4  # Number of parallel jobs


def yt_dlp_worker(job_id, url):
    job_output_dir = os.path.join(shared_output_root, job_id)
    os.makedirs(job_output_dir, exist_ok=True)
    logging.info(f"[Worker] Starting job {job_id} for URL: {url}")
    result = {
        "status": "running",
        "started_at": time.time(),
        "url": url,
        "result_path": None,
        "original_path": None,
        "error": None,
    }
    try:
        file_path = run_yt_dlp(url, job_output_dir, job_id, timeout=MAX_JOB_SECONDS)
        if not file_path:
            result["status"] = "failed"
            result["error"] = "yt-dlp failed or no file"
            logging.error(f"[Worker] Job {job_id} failed: yt-dlp failed or no file")
            shutil.rmtree(job_output_dir, ignore_errors=True)
            return result
        result["original_path"] = file_path
        logging.info(f"[Worker] Job {job_id} downloaded file: {file_path}")
        result_path = compress_file_if_needed(file_path, timeout=MAX_JOB_SECONDS)
        result["result_path"] = result_path
        if result_path:
            result["status"] = "done"
            result["finished_at"] = time.time()
            logging.info(f"[Worker] Job {job_id} completed. Result file: {result_path}")
        else:
            result["status"] = "failed"
            result["error"] = "Compression failed or file too large"
            result["finished_at"] = time.time()
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
        result["status"] = "failed"
        result["error"] = str(e)
        result["finished_at"] = time.time()
        logging.exception(f"[Worker] Job {job_id} encountered an exception:")
        shutil.rmtree(job_output_dir, ignore_errors=True)
    return result


executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


@app.route("/health", methods=["GET"])
def health():
    ytdlp_version = None
    try:
        ytdlp_version = (
            subprocess.check_output(["yt-dlp", "--version"]).decode().strip()
        )
    except Exception as e:
        ytdlp_version = str(e)
    job_count = len(jobs)
    job_ids = list(jobs.keys())
    return (
        jsonify(
            {
                "status": "ok",
                "yt-dlp_version": ytdlp_version,
                "jobs": job_count,
                "job_ids": job_ids,
            }
        ),
        200,
    )


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "Missing url"}), 400
    job_id = str(uuid.uuid4())
    # Submit the job to the executor
    future = executor.submit(yt_dlp_worker, job_id, url)
    jobs[job_id] = {
        "status": "queued",
        "url": url,
        "future": future,
        "created_at": time.time(),
        "result_path": None,
        "original_path": None,
        "error": None,
    }
    logging.info(f"[Submit] New job submitted: {job_id} for URL: {url}")
    return jsonify({"job_id": job_id}), 200


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    future = job.get("future")
    if future is not None:
        if future.done():
            result = future.result()
            # Update job dict with result
            job.update(result)
        else:
            job["status"] = "running"
    logging.info(f"[Status] Job {job_id} status requested.")
    return jsonify({"status": job["status"], "error": job.get("error")}), 200


@app.route("/result/<job_id>", methods=["GET"])
def result(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    future = job.get("future")
    if future is not None and future.done():
        result = future.result()
        job.update(result)
    if job["status"] != "done" or not job["result_path"]:
        return jsonify({"error": "Job not complete"}), 400
    result_path = job["result_path"]
    logging.info(f"[Result] Job {job_id} result requested.")
    try:
        return send_file(result_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cleanup/<job_id>", methods=["POST"])
def cleanup(job_id):
    job = jobs.get(job_id)
    if not job:
        logging.info(f"[Cleanup] Job {job_id} not found for cleanup.")
        return jsonify({"error": "Job not found"}), 404
    future = job.get("future")
    if future is not None and future.done():
        result = future.result()
        job.update(result)
    if job["status"] not in ("done", "failed"):
        return jsonify({"error": "Job not done or failed yet"}), 400
    result_path = job.get("result_path")
    job_output_dir = os.path.dirname(result_path) if result_path else None
    try:
        if result_path and os.path.isfile(result_path):
            os.remove(result_path)
            logging.info(
                f"[Cleanup] Deleted result file for job {job_id}: {result_path}"
            )
        if job_output_dir and os.path.isdir(job_output_dir):
            shutil.rmtree(job_output_dir, ignore_errors=True)
            logging.info(
                f"[Cleanup] Deleted job directory for job {job_id}: {job_output_dir}"
            )
        jobs.pop(job_id, None)
        logging.info(f"[Cleanup] Removed job metadata for job {job_id}")
        return jsonify({"status": "cleaned"}), 200
    except Exception as e:
        logging.exception(f"[Cleanup] Exception while cleaning up job {job_id}:")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
