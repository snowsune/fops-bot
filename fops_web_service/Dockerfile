FROM python:3.11-slim

# Authors
LABEL authors="vixi@snowsue.net"

# Set the name of our app
ARG APP_NAME=fops-web-service
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
RUN apt update && apt install -y python-dev-is-python3 curl

# Copy requirements and install
COPY requirements.txt ./
RUN pip install -r requirements.txt --no-cache-dir

# Copy the web service files
COPY . .

# Drop root and change ownership of /app to app:app
RUN chown -R ${USER_ID}:${GROUP_ID} /app
USER ${USER_ID}

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "app:app"] 