"""
Flask-based dashboard for Fops Bot. Run with start_dashboard(bot) from your bot's startup code.
"""

import threading
import time
import os
from flask import Flask, render_template, send_from_directory
import markdown2
import textwrap

# These will be set by the bot at runtime
bot_instance = None
bot_start_time = time.time()

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)


@app.route("/")
def dashboard():
    if bot_instance is None:
        return "Bot not initialized!"

    # Gather stats
    version = getattr(bot_instance, "version", "Unknown")
    uptime_seconds = int(time.time() - bot_start_time)
    uptime = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
    guild_count = len(getattr(bot_instance, "guilds", []))
    # Usage count: expects bot_instance.usage_today to exist, else 0
    usage_today = getattr(bot_instance, "usage_today", 0)

    # Gather commands and docstrings
    commands = []
    if hasattr(bot_instance, "tree") and hasattr(bot_instance.tree, "get_commands"):
        for c in bot_instance.tree.get_commands():
            doc = c.callback.__doc__ or ""
            doc = textwrap.dedent(doc).strip()
            if not doc:
                continue
            doc_html = markdown2.markdown(doc)
            commands.append(
                {
                    "name": c.name,
                    "help": doc_html,
                }
            )
    elif hasattr(bot_instance, "commands"):
        for c in bot_instance.commands:
            doc = getattr(c, "help", "")
            doc = textwrap.dedent(doc).strip()
            if not doc:
                continue
            doc_html = markdown2.markdown(doc)
            commands.append(
                {
                    "name": getattr(c, "name", str(c)),
                    "help": doc_html,
                }
            )

    return render_template(
        "dashboard.html",
        version=version,
        uptime=uptime,
        guild_count=guild_count,
        usage_today=usage_today,
        commands=commands,
    )


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


def run_dashboard(host="0.0.0.0", port=8080):
    app.run(host=host, port=port, debug=False, use_reloader=False)


def start_dashboard(bot, start_time=None):
    global bot_instance, bot_start_time
    bot_instance = bot
    if start_time:
        bot_start_time = start_time
    # TEMPORARILY DISABLED: Flask subsystem is disabled until Gunicorn hosting is set up.
    # thread = threading.Thread(target=run_dashboard, daemon=True)
    # thread.start()


if __name__ == "__main__":
    # TEMPORARILY DISABLED: Flask subsystem is disabled until Gunicorn hosting is set up.
    # app.run(host="0.0.0.0", port=5000)
    pass
