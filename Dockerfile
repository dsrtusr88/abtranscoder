FROM ghcr.io/hotio/base:alpinevpn-5b6ec6c

RUN apk update && apk upgrade

# Install system packages
RUN apk add --no-cache \
    python3 \
    py3-pip \
    git \
    mktorrent \
    flac \
    lame \
    sox \
    ffmpeg \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    zlib-dev \
    py3-lxml \
    && apk add --no-cache py3-packaging # Separate apk add instruction for py3-packaging

# Install tzdata
RUN apk add --no-cache tzdata && \
    apk add --no-cache jpeg-dev # Install libjpeg-dev equivalent package in Alpine

RUN apk add --no-cache build-base python3-dev jpeg-dev zlib-dev
RUN pip install --no-cache-dir --no-binary :all: --no-build-isolation Pillow

# Copy application files
COPY / "${APP_DIR}"

# Install Python dependencies
RUN pip3 install --no-cache-dir -r "${APP_DIR}"/requirements.txt && \
    pip3 install --no-cache-dir Pillow

# Set arguments and permissions
ARG VERSION
ARG GIT_BRANCH
RUN chmod -R u=rwX,go=rX "${APP_DIR}" && \
    echo "v${VERSION}" > "${APP_DIR}/version.txt" && \
    echo "${GIT_BRANCH}" > "${APP_DIR}/branch.txt" && \
    chmod +x "${APP_DIR}"/start.sh

# Set entry point
ENTRYPOINT "${APP_DIR}"/start.sh
