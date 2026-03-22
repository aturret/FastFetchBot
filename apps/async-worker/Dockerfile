
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
    VENV_PATH="/opt/pysetup/.venv"

# prepend venv to path
ENV PATH="$VENV_PATH/bin:$PATH"


# `builder-base` stage is used to build deps + create our virtual environment
FROM python-base AS builder-base

# install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        ca-certificates \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# copy workspace files for dependency resolution
WORKDIR $PYSETUP_PATH
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/async-worker/ apps/async-worker/

# install runtime deps
RUN uv sync --frozen --no-dev --no-install-project --package fastfetchbot-async-worker


# `production` image used for runtime
FROM python-base AS production
ENV PYTHONPATH=/app/apps/async-worker:$PYTHONPATH
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH
COPY packages/ /app/packages/
COPY apps/async-worker/ /app/apps/async-worker/
WORKDIR /app/apps/async-worker
CMD ["arq", "async_worker.main.WorkerSettings"]
