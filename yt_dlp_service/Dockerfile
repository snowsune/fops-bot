FROM python:3.11-slim

# Authors
LABEL authors="vixi@snowsue.net"

# App home
ARG HOME="/app"
ENV HOME=${HOME}
WORKDIR ${HOME}

# Install any deps we need
RUN apt update && apt install ffmpeg curl -y

# Add /bin to path
RUN mkdir -p ${HOME}/bin
ENV PATH $PATH:${HOME}/bin

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ${HOME}/bin/yt-dlp
RUN chmod a+rx ${HOME}/bin/yt-dlp
RUN yt-dlp -U

# Install Requirements
ADD requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy in all else
COPY . .

# Health check via Redis ping
HEALTHCHECK CMD python -c "import redis; r=redis.Redis(host='redis', port=6379, db=0); exit(0 if r.ping() else 1)"

CMD ["python", "app.py"]
