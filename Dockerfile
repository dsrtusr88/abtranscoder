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

# Set the working directory in the container
WORKDIR /app

# Copy application files
COPY . /app

# Install Pillow dependencies
RUN pip install --no-cache-dir Pillow

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set arguments and permissions
ARG VERSION
ARG GIT_BRANCH
RUN chmod -R u=rwX,go=rX /app && \
    echo "v${VERSION}" > /app/version.txt && \
    echo "${GIT_BRANCH}" > /app/branch.txt && \
    chmod +x /app/start.sh

# Set entry point
#ENTRYPOINT ["/app/start.sh"]
# Directly start the Python script for debugging
CMD ["python3", "/app/main.py"]
