FROM ghcr.io/hotio/base:alpinevpn-5b6ec6c

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
    py3-packaging \   # Move py3-packaging to separate apk add instruction
    tzdata \
    && pip3 install --no-cache-dir --upgrade pip setuptools
	
COPY / "${APP_DIR}"

RUN pip3 install --no-cache-dir -r "${APP_DIR}"/requirements.txt \
    && pip3 install --no-cache-dir Pillow
    
ARG VERSION
ARG GIT_BRANCH

RUN chmod -R u=rwX,go=rX "${APP_DIR}" && \
    echo "v${VERSION}" > "${APP_DIR}/version.txt" && \
    echo "${GIT_BRANCH}" > "${APP_DIR}/branch.txt" && \
    chmod +x "${APP_DIR}"/start.sh

ENTRYPOINT "${APP_DIR}"/start.sh
