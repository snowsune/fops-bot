#!/bin/bash
set -e

# Build the Docker image with tag 'local'
docker build -t fops_bot:local ./fops_bot

# Set TAG=local for docker compose
export TAG=local

# Start the stack
docker-compose up