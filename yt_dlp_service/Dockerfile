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

EXPOSE 5000

# The `|| exit 1` isn't required but it's good practice anyway.
HEALTHCHECK CMD CURL http://localhost:5000/health || exit 1

CMD ["python", "app.py"]
