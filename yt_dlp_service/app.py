import threading
import uuid
import time
import os
import shutil
import logging
from flask import Flask, jsonify, request, send_file
from yt_dlp_logic import run_yt_dlp, compress_file_if_needed, cleanup_files

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s"
)

app = Flask(__name__)

jobs = {}
queue = []
shared_output_root = "/tmp/yt_dlp_output"
os.makedirs(shared_output_root, exist_ok=True)


def worker():
    """
    Backgound worker for yt-dlp
    For each job:
      - Creates a unique output directory for the job.
      - Runs yt-dlp to download the media to that directory.
      - Compresses the file if needed.
      - Updates job status and stores the result path.
      - Cleans up all files except the result file.
      - On failure, cleans up the entire job directory.
    """

    while True:
        if queue:
            job_id = queue.pop(0)
            job = jobs[job_id]
            jobs[job_id]["status"] = "running"
            url = job["url"]
            job_output_dir = os.path.join(shared_output_root, job_id)
            os.makedirs(job_output_dir, exist_ok=True)
            logging.info(f"[Worker] Starting job {job_id} for URL: {url}")
            try:
                # Download the media using yt-dlp
                file_path = run_yt_dlp(url, job_output_dir, job_id)
                if not file_path:
                    jobs[job_id]["status"] = "failed"
                    jobs[job_id]["error"] = "yt-dlp failed or no file"
                    logging.error(
                        f"[Worker] Job {job_id} failed: yt-dlp failed or no file"
                    )
                    shutil.rmtree(job_output_dir, ignore_errors=True)
                    continue
                jobs[job_id]["original_path"] = file_path
                logging.info(f"[Worker] Job {job_id} downloaded file: {file_path}")
                # Compress the file if it exceeds the size limit
                result_path = compress_file_if_needed(file_path)
                jobs[job_id]["result_path"] = result_path
                if result_path:
                    jobs[job_id]["status"] = "done"
                    logging.info(
                        f"[Worker] Job {job_id} completed. Result file: {result_path}"
                    )
                else:
                    jobs[job_id]["status"] = "failed"
                    jobs[job_id]["error"] = "Compression failed or file too large"
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
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = str(e)
                logging.exception(f"[Worker] Job {job_id} encountered an exception:")
                shutil.rmtree(job_output_dir, ignore_errors=True)
        else:
            time.sleep(1)


# Start background worker thread
t = threading.Thread(target=worker, daemon=True)
t.start()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "Missing url"}), 400
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "url": url, "result_path": None}
    queue.append(job_id)
    logging.info(f"[Submit] New job submitted: {job_id} for URL: {url}")
    return jsonify({"job_id": job_id}), 200


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    logging.info(f"[Status] Job {job_id} status requested.")
    return jsonify({"status": job["status"], "error": job.get("error")}), 200


@app.route("/result/<job_id>", methods=["GET"])
def result(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] != "done" or not job["result_path"]:
        return jsonify({"error": "Job not complete"}), 400
    logging.info(f"[Result] Job {job_id} result requested.")
    try:
        return send_file(job["result_path"], as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cleanup/<job_id>", methods=["POST"])
def cleanup(job_id):
    """
    Fops in most circumstances can just let us know when its
    posted/used the file and its ready to be deleted early.
    """

    job = jobs.get(job_id)
    if not job:
        logging.info(f"[Cleanup] Job {job_id} not found for cleanup.")
        return jsonify({"error": "Job not found"}), 404

    # Remove result file and job directory
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
