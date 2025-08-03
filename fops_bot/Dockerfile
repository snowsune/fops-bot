FROM python:3.11-slim

# Authors
LABEL authors="vixi@snowsue.net"

# Set the name of our app
ARG APP_NAME=fops-bot
ENV APP_NAME=${APP_NAME}

# App home
ARG HOME="/app"
ENV HOME=${HOME}

# Upgrade pip
RUN pip install --upgrade pip --no-cache-dir

# Set workdir
WORKDIR ${HOME}
ENV PYTHONPATH=/app

# Add any packages we need
RUN apt update && apt install -y python-dev-is-python3 curl libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev

# Copy requirements, setup.py, alembic.ini, and bin to /app
COPY README.md ./
COPY requirements.txt ./
COPY setup.py ./
COPY alembic.ini ./
COPY bin ./bin

# Add bin to PATH
ENV PATH $PATH:/app/bin

# Install requirements
RUN pip install -r requirements.txt --no-cache-dir

# Copy the fops_bot, utilities, and cogs
COPY . .

# Install our app as a package
RUN pip install -e /app

# Drop root and change ownership of /app to app:app
RUN chown -R ${USER_ID}:${GROUP_ID} /app
USER ${USER_ID}

# The `|| exit 1` isn't required but it's good practice anyway.
HEALTHCHECK CMD discordhealthcheck || exit 1

# Run the entrypoint bin
ENTRYPOINT ["entrypoint"]
