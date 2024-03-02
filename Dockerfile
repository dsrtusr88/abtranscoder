FROM python:3.9-slim

# Install system packages
RUN apt-get update && apt-get install -y \
    git \
    mktorrent \
    flac \
    lame \
    sox \
    ffmpeg \
    build-essential \
    python3-dev \
    libjpeg-dev \
    zlib1g-dev \
    libffi-dev \
    libssl-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Pillow dependencies
RUN pip install --no-cache-dir Pillow

# Set the working directory in the container
APP_DIR /app

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set entry point
ENTRYPOINT "${APP_DIR}"/start.sh
