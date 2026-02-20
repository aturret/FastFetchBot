
# `python-base` sets up all our shared environment variables
FROM python:3.12-slim AS python-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # uv settings
    UV_PROJECT_ENVIRONMENT="/opt/pysetup/.venv" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # paths
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv" \
    DENO_INSTALL="/root/.deno"

# prepend venv to path
ENV PATH="$DENO_INSTALL/bin:$VENV_PATH/bin:$PATH"


# `builder-base` stage is used to build deps + create our virtual environment
FROM python-base AS builder-base

# install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        ca-certificates \
        ffmpeg \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libjpeg-dev \
        libopenjp2-7-dev \
        libffi-dev \
        build-essential \
        fonts-wqy-microhei \
        fonts-wqy-zenhei \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
    && curl -fsSL https://deno.land/install.sh | sh

# copy workspace files for dependency resolution
WORKDIR $PYSETUP_PATH
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/worker/ apps/worker/

# install runtime deps
RUN uv sync --frozen --no-dev --no-install-project --package fastfetchbot-worker


# `production` image used for runtime
FROM python-base AS production
ENV PYTHONPATH=/app/apps/worker:$PYTHONPATH
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        ffmpeg \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libjpeg-dev \
        libopenjp2-7-dev \
        libffi-dev \
        fonts-wqy-microhei \
        fonts-wqy-zenhei \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder-base /root/.deno /root/.deno
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH
COPY packages/ /app/packages/
COPY apps/worker/ /app/apps/worker/
WORKDIR /app/apps/worker
CMD ["celery", "-A", "worker_core.main:app", "worker", "--loglevel=info", "--concurrency=2"]
