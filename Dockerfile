
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
    PLAYWRIGHT_BROWSERS_PATH="/opt/playwright-browsers"

# prepend venv to path
ENV PATH="$VENV_PATH/bin:$PATH"


# `builder-base` stage is used to build deps + create our virtual environment
FROM python-base AS builder-base

# install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        ffmpeg \
        libmagic1 \
        # deps for building python deps \
        # deps for weasyprint
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libjpeg-dev \
        libopenjp2-7-dev \
        libffi-dev \
        build-essential \
        fonts-wqy-microhei \
        fonts-wqy-zenhei \
        fonts-noto-cjk \
        fonts-noto-cjk-extra

# copy project requirement files here to ensure they will be cached.
WORKDIR $PYSETUP_PATH
COPY uv.lock pyproject.toml ./

# install runtime deps - uses $UV_PROJECT_ENVIRONMENT internally
RUN uv sync --frozen --no-dev --no-install-project

# install the browser dependencies for playwright
RUN uv run playwright install --with-deps


# `production` image used for runtime
FROM python-base AS production
ENV FASTAPI_ENV=production
ENV PYTHONPATH=/app:$PYTHONPATH
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        ffmpeg \
        libmagic1 \
        # deps for building python deps \
        # deps for weasyprint
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libjpeg-dev \
        libopenjp2-7-dev \
        libffi-dev \
        fonts-wqy-microhei \
        fonts-wqy-zenhei \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxdamage1
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH
COPY --from=builder-base $PLAYWRIGHT_BROWSERS_PATH $PLAYWRIGHT_BROWSERS_PATH
COPY ./ /app
WORKDIR /app
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--preload"]
