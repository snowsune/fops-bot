# Fops Web Service

A Flask-based web dashboard for the Fops Bot, served with Gunicorn.

## Purpose

This service provides a web interface to view bot statistics, including:
- Bot version and uptime
- Number of guilds the bot is in
- Daily command usage
- List of available commands with help text

## Architecture

The web service communicates with the main bot via a simple HTTP API endpoint (`/api/stats`) that the bot exposes on port 5000. This allows the web service to be completely separate from the bot while still accessing real-time data.

## Setup

The service is designed to run as a Docker container alongside the main bot. It requires:

- The bot to be running and exposing its API on port 5000
- Environment variable `BOT_API_URL` pointing to the bot's API endpoint (defaults to `http://fops_bot:5000`)

## Development

To run locally:

```bash
cd fops_web_service
pip install -r requirements.txt
python app.py
```

The dashboard will be available at `http://localhost:8080`.

## Production

In production, the service runs with Gunicorn for better performance and reliability. The Docker container automatically starts with the appropriate Gunicorn configuration. 