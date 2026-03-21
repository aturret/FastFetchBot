# CLAUDE.md

## Project Overview

FastFetchBot is a social media content fetching service built as a **UV workspace monorepo** with three microservices: a FastAPI server (API), a Telegram Bot client, and a Celery worker for file operations. It scrapes and archives content from various social media platforms including Twitter, Weibo, Xiaohongshu, Reddit, Bluesky, Instagram, Zhihu, Douban, YouTube, and Bilibili.

## Architecture

```
FastFetchBot/
├── packages/shared/          # fastfetchbot-shared: common models, utilities, logger
├── packages/file-export/     # fastfetchbot-file-export: video download, PDF export, transcription
├── apps/api/                 # FastAPI server: scrapers, storage, routing
├── apps/telegram-bot/        # Telegram Bot: webhook/polling, message handling
├── apps/worker/              # Celery worker: async file operations (video, PDF, audio)
├── pyproject.toml            # Root workspace configuration
└── uv.lock                   # Lockfile for the entire workspace
```

| Service | Package Name | Port | Entry Point |
|---------|-------------|------|-------------|
| **API Server** (`apps/api/src/`) | `fastfetchbot-api` | 10450 | `gunicorn -k uvicorn.workers.UvicornWorker src.main:app --preload` |
| **Telegram Bot** (`apps/telegram-bot/core/`) | `fastfetchbot-telegram-bot` | 10451 | `python -m core.main` |
| **Worker** (`apps/worker/worker_core/`) | `fastfetchbot-worker` | — | `celery -A worker_core.main:app worker --loglevel=info --concurrency=2` |
| **Shared Library** (`packages/shared/fastfetchbot_shared/`) | `fastfetchbot-shared` | — | — |
| **File Export Library** (`packages/file-export/fastfetchbot_file_export/`) | `fastfetchbot-file-export` | — | — |

The Telegram Bot communicates with the API server over HTTP (`API_SERVER_URL`). In Docker, this is `http://api:10450`.

### API Server (`apps/api/src/`)

- **`main.py`** — FastAPI app setup, Sentry integration, lifecycle management
- **`config.py`** — Environment variable handling, platform credentials
- **`routers/`** — `scraper.py` (generic endpoint), `scraper_routers.py` (platform-specific), `inoreader.py`, `wechat.py`
- **`services/scrapers/`** — `scraper_manager.py` orchestrates platform scrapers (twitter, weibo, bluesky, xiaohongshu, reddit, instagram, zhihu, douban, threads, wechat, general); the Xiaohongshu scraper uses `xiaohongshu/adaptar.py` (`XhsSinglePostAdapter`) with an external sign server instead of the old Playwright-based crawler
- **`services/file_export/`** — PDF generation, audio transcription (OpenAI), video download
- **`services/amazon/s3.py`** — S3 storage integration
- **`services/telegraph/`** — Telegraph content publishing
- **`templates/`** — Jinja2 templates for platform-specific output formatting

### Telegram Bot (`apps/telegram-bot/core/`)

- **`main.py`** — Entry point
- **`api_client.py`** — HTTP client calling the API server
- **`handlers/`** — `messages.py`, `buttons.py`, `url_process.py`
- **`services/`** — `bot_app.py`, `message_sender.py`, `constants.py`
- **`webhook/server.py`** — Webhook/polling server
- **`templates/`** — Jinja2 templates for bot messages

### Shared Library (`packages/shared/fastfetchbot_shared/`)

- **`config.py`** — URL patterns (SOCIAL_MEDIA_WEBSITE_PATTERNS, VIDEO_WEBSITE_PATTERNS, BANNED_PATTERNS); shared env vars including `SIGN_SERVER_URL` and `XHS_COOKIE_PATH`
- **`models/`** — `classes.py` (NamedBytesIO), `metadata_item.py`, `telegraph_item.py`, `url_metadata.py`
- **`utils/`** — `parse.py` (URL parsing, HTML processing, `get_env_bool`), `image.py`, `logger.py`, `network.py`

## Development Commands

### Package Management
- `uv sync` — Install all dependencies (including dev)
- `uv lock` — Regenerate the lock file after pyproject.toml changes

### Running Locally

```bash
# API server
cd apps/api
uv run gunicorn -k uvicorn.workers.UvicornWorker src.main:app --preload

# Telegram Bot (separate terminal)
cd apps/telegram-bot
uv run python -m core.main
```

### Testing
- `uv run pytest` — Run all tests
- `uv run pytest tests/test_bluesky.py` — Run specific test file
- `uv run pytest -v` — Verbose output

### Code Formatting
- `uv run black .` — Format all Python code

### Docker

```bash
# Start all services (uses pre-built images from GHCR)
docker-compose up -d

# Build locally
docker build -f apps/api/Dockerfile -t fastfetchbot-api .
docker build -f apps/telegram-bot/Dockerfile -t fastfetchbot-telegram-bot .
docker build -f apps/worker/Dockerfile -t fastfetchbot-worker .
```

> **uv version in Docker**: All three Dockerfiles pin uv to `0.10.4` via `COPY --from=ghcr.io/astral-sh/uv:0.10.4`.
> To upgrade, update that tag in `apps/api/Dockerfile`, `apps/telegram-bot/Dockerfile`, and `apps/worker/Dockerfile`.

Docker Compose services (see `docker-compose.template.yml`):
- **api** — API server (port 10450)
- **telegram-bot** — Telegram Bot (port 10451)
- **telegram-bot-api** — Local Telegram Bot API for large file support (ports 8081-8082)
- **redis** — Message broker and result backend for Celery (port 6379)
- **worker** — Celery worker for file operations (video download, PDF export, audio transcription)

## Environment Configuration

See `template.env` for a complete reference. Key variables:

### Required
| Variable | Description |
|----------|-------------|
| `BASE_URL` | Public server domain (used for webhook URL construction) |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Default chat ID for the bot |

### Service Communication (Docker)
| Variable | Default | Description |
|----------|---------|-------------|
| `API_SERVER_URL` | `http://localhost:10450` | URL the Telegram Bot uses to call the API. `http://api:10450` in Docker. |
| `TELEGRAM_BOT_CALLBACK_URL` | `http://localhost:10451` | URL the API uses to call the Telegram Bot. `http://telegram-bot:10451` in Docker. |
| `TELEGRAM_BOT_MODE` | `polling` | `polling` (dev) or `webhook` (production with HTTPS) |

### Platform Credentials
- Most scrapers require authentication cookies/tokens
- Use browser extension "Get cookies.txt LOCALLY" to extract cookies
- Store Zhihu cookies in `conf/zhihu_cookies.json`
- Store Xiaohongshu cookies in `conf/xhs_cookies.txt` (single-line cookie string, e.g. `a1=x; web_id=x; web_session=x`)
- Xiaohongshu also requires an external **sign server** reachable at `SIGN_SERVER_URL` (default `http://localhost:8989`); the sign server is currently closed-source — you must supply your own compatible implementation
- See `template.env` for all platform-specific variables (Twitter, Weibo, Xiaohongshu, Reddit, Instagram, Bluesky, etc.)

### Database
- Optional MongoDB integration (`DATABASE_ON=true`)
- Uses Beanie ODM for async operations

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) builds and pushes all three images on push to `main`:
- `ghcr.io/aturret/fastfetchbot-api:latest`
- `ghcr.io/aturret/fastfetchbot-tgbot:latest`
- `ghcr.io/aturret/fastfetchbot-worker:latest`

## Development Guidelines

### Adding a New Platform Scraper
1. Create scraper module in `apps/api/src/services/scrapers/<platform>/`
2. Implement scraper class following existing patterns
3. Add platform-specific router in `apps/api/src/routers/`
4. Register the scraper in `ScraperManager`
5. Add configuration variables in `apps/api/src/config.py`
6. Create tests in `tests/cases/`

### Key Conventions
- Shared models and utilities go in `packages/shared/fastfetchbot_shared/`
- API-specific code goes in `apps/api/src/`
- Telegram bot code goes in `apps/telegram-bot/core/`
- The bot communicates with the API only via HTTP — no direct imports of API code
- Jinja2 templates for output formatting, with i18n support via Babel
- Loguru for logging, Sentry for production error monitoring
- Store sensitive cookies/tokens in environment variables, never in code
