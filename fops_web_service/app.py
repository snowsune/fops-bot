"""
Flask-based dashboard for Fops Bot.
This service fetches data from the bot's API endpoint and serves the dashboard.
"""

import os
import time
import requests
from flask import Flask, render_template, send_from_directory
import markdown2
import textwrap

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)

# Bot API endpoint
BOT_API_URL = os.environ.get("BOT_API_URL", "http://fops_bot:5000")


def fetch_bot_data():
    """Fetch data from the bot's API endpoint"""
    try:
        response = requests.get(f"{BOT_API_URL}/api/stats", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching bot data: {e}")

    # Return default data if API call fails
    return {
        "version": os.environ.get("GIT_COMMIT", "Unknown"),
        "start_time": time.time(),
        "guild_count": 0,
        "usage_today": 0,
        "commands": [],
    }


@app.route("/")
def dashboard():
    # Fetch bot data
    bot_data = fetch_bot_data()

    # Calculate uptime
    uptime_seconds = int(time.time() - bot_data.get("start_time", time.time()))
    uptime = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"

    # Process commands
    commands = []
    for cmd in bot_data.get("commands", []):
        if cmd.get("help"):
            doc_html = markdown2.markdown(cmd["help"])
            commands.append(
                {
                    "name": cmd["name"],
                    "help": doc_html,
                }
            )

    return render_template(
        "dashboard.html",
        version=bot_data.get("version", "Unknown"),
        uptime=uptime,
        guild_count=bot_data.get("guild_count", 0),
        usage_today=bot_data.get("usage_today", 0),
        commands=commands,
    )


@app.route("/static/<path:filename>")
def static_files(filename):
    static_folder = app.static_folder
    if static_folder is None:
        return "Static folder not configured", 500
    return send_from_directory(static_folder, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
