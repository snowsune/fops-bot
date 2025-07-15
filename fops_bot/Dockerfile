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
RUN apt update && apt install python-dev-is-python3 curl -y

# Copy in all requirements
ADD requirements.txt .

# Install normal reqs
RUN pip install -r requirements.txt --no-cache-dir

# Add alembic
ADD alembic.ini .

# Add /bin to path
RUN mkdir -p ${HOME}/bin
ENV PATH $PATH:${HOME}/bin

# Copy in everything else
ADD . ${HOME}

# Get the current git version
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

# Install our app in edit mode using pip
RUN pip install -e ${HOME} --no-cache-dir

# Drop root and change ownership of /app to app:app
RUN chown -R ${USER_ID}:${GROUP_ID} ${HOME}
USER ${USER_ID}

# The `|| exit 1` isn't required but it's good practice anyway.
HEALTHCHECK CMD discordhealthcheck || exit 1

# Run the entrypoint bin
ENTRYPOINT ["entrypoint"]
