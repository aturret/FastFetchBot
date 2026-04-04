# CLAUDE.md

## Project Overview

FastFetchBot is a social media content fetching service built as a **UV workspace monorepo** with four microservices: a FastAPI server (API), a Telegram Bot client, a Celery worker for file operations, and an ARQ-based async worker for off-path scraping and file_id persistence. It scrapes and archives content from various social media platforms including Twitter, Weibo, Xiaohongshu, Reddit, Bluesky, Instagram, Zhihu, Douban, YouTube, and Bilibili.

## Architecture

```
FastFetchBot/
├── packages/shared/          # fastfetchbot-shared: scrapers, telegraph, models, utilities
│   └── fastfetchbot_shared/
│       ├── config.py         # URL patterns, shared env vars
│       ├── models/           # UrlMetadata, MetadataItem, NamedBytesIO, etc.
│       ├── utils/            # parse, image, logger, network, cookie
│       ├── database/
│       │   ├── base.py, engine.py, session.py  # SQLAlchemy (user settings)
│       │   ├── models/user_setting.py          # UserSetting SQLAlchemy model
│       │   └── mongodb/                        # Beanie ODM (scraped content)
│       │       ├── connection.py   # init_mongodb(), close_mongodb(), save_instances()
│       │       ├── cache.py        # find_cached(), save_metadata() — URL-based cache with TTL + versioning
│       │       └── models/metadata.py  # Metadata Document, DatabaseMediaFile
│       └── services/
│           ├── scrapers/     # All platform scrapers + ScraperManager + InfoExtractService
│           │   ├── config.py # ALL scraper env vars (platform creds, Firecrawl, Zyte, Telegraph tokens)
│           │   ├── common.py # Core InfoExtractService (scraping + MongoDB cache lookup)
│           │   ├── scraper_manager.py
│           │   ├── scraper.py          # Base Scraper + DataProcessor ABCs
│           │   ├── templates/          # 13 Jinja2 templates for platform output formatting
│           │   ├── twitter/  bluesky/  weibo/  xiaohongshu/  reddit/
│           │   ├── instagram/  zhihu/  douban/  threads/  wechat/
│           │   └── general/            # Firecrawl + Zyte generic scraping
│           ├── file_export/  # Async Celery task wrappers (PDF, video, audio transcription)
│           └── telegraph/    # Telegraph content publishing
├── packages/file-export/     # fastfetchbot-file-export: synchronous Celery worker jobs (yt-dlp, WeasyPrint, OpenAI)
├── apps/api/                 # FastAPI server: enriched service, routing, storage
├── apps/telegram-bot/        # Telegram Bot: webhook/polling, message handling
├── apps/worker/              # Celery worker: sync file operations (video, PDF, audio)
├── apps/async-worker/        # ARQ async worker: off-path scraping + enrichment + file_id persistence
├── pyproject.toml            # Root workspace configuration
└── uv.lock                   # Lockfile for the entire workspace
```

| Service | Package Name | Port | Entry Point |
|---------|-------------|------|-------------|
| **API Server** (`apps/api/src/`) | `fastfetchbot-api` | 10450 | `gunicorn -k uvicorn.workers.UvicornWorker src.main:app --preload` |
| **Telegram Bot** (`apps/telegram-bot/core/`) | `fastfetchbot-telegram-bot` | 10451 | `python -m core.main` |
| **Worker** (`apps/worker/worker_core/`) | `fastfetchbot-worker` | — | `celery -A worker_core.main:app worker --loglevel=info --concurrency=2` |
| **Async Worker** (`apps/async-worker/async_worker/`) | `fastfetchbot-async-worker` | — | `arq async_worker.main.WorkerSettings` |
| **Shared Library** (`packages/shared/fastfetchbot_shared/`) | `fastfetchbot-shared` | — | — |
| **File Export Library** (`packages/file-export/fastfetchbot_file_export/`) | `fastfetchbot-file-export` | — | — |

The Telegram Bot communicates with the API server over HTTP (`API_SERVER_URL`). In Docker, this is `http://api:10450`.

### API Server (`apps/api/src/`)

- **`main.py`** — FastAPI app setup, Sentry integration, lifecycle management
- **`config.py`** — API-only env vars: BASE_URL, API_KEY, DATABASE_ON, MongoDB, Celery, AWS S3, Inoreader, locale/i18n. **No scraper credentials** (those live in `fastfetchbot_shared.services.scrapers.config`)
- **`routers/`** — `scraper.py` (generic endpoint), `scraper_routers.py` (platform-specific), `inoreader.py`, `wechat.py`
- **`services/scrapers/common.py`** — `InfoExtractService` (enriched): extends core `InfoExtractService` from shared with Telegraph publishing, PDF export, DB storage (via `save_metadata()`), and video download (youtube/bilibili). Defaults `database_cache_ttl` from `settings.DATABASE_CACHE_TTL`. Skips enrichment on cache hits via `_cached` flag
- **`database.py`** — Thin wrapper delegating to `fastfetchbot_shared.database.mongodb` (init/close/save)
- **`models/database_model.py`** — Re-export wrapper for `Metadata` from shared
- **`services/file_export/`** — PDF generation, audio transcription (OpenAI), video download
- **`services/amazon/s3.py`** — S3 storage integration
- **`services/telegraph/`** — Re-export wrapper: `from fastfetchbot_shared.services.telegraph import Telegraph`

### Telegram Bot (`apps/telegram-bot/core/`)

- **`main.py`** — Entry point
- **`api_client.py`** — HTTP client calling the API server
- **`queue_client.py`** — ARQ Redis client for enqueuing scrape jobs (queue mode)
- **`handlers/`** — `messages.py`, `buttons.py`, `url_process.py`, `commands.py` (start, /settings with inline toggles)
- **`services/`** — `bot_app.py`, `message_sender.py` (media packaging with file_id shortcut + background file_id capture), `file_id_capture.py` (extracts file_ids from sent messages, pushes to Redis for async worker persistence), `user_settings.py` (get/toggle `auto_fetch_in_dm` and `force_refresh_cache`), `constants.py`
- **`webhook/server.py`** — Webhook/polling server
- **`templates/`** — Jinja2 templates for bot messages

### Async Worker (`apps/async-worker/async_worker/`)

- **`main.py`** — ARQ worker entry point with `on_startup`/`on_shutdown` hooks for MongoDB and file_id consumer lifecycle
- **`config.py`** — `AsyncWorkerSettings` with MongoDB, Redis, and runtime flags (`file_id_consumer_ready`)
- **`services/file_id_consumer.py`** — Background Redis BRPOP consumer for `fileid:updates` queue. Receives file_id payloads from the Telegram bot, matches media URLs to the latest `Metadata` document in MongoDB, and persists `telegram_file_id` values. Lifecycle managed via `start()`/`stop()` during worker startup/shutdown when `DATABASE_ON` is true

### Shared Library (`packages/shared/fastfetchbot_shared/`)

- **`config.py`** — URL patterns (SOCIAL_MEDIA_WEBSITE_PATTERNS, VIDEO_WEBSITE_PATTERNS, BANNED_PATTERNS); shared env vars including `SIGN_SERVER_URL` and `XHS_COOKIE_PATH`
- **`models/`** — `classes.py` (NamedBytesIO), `metadata_item.py` (MediaFile with optional `telegram_file_id` for Telegram file_id caching, MetadataItem, MessageType), `telegraph_item.py`, `url_metadata.py`
- **`utils/`** — `parse.py` (URL parsing, HTML processing, `get_env_bool`), `image.py`, `logger.py`, `network.py`, `cookie.py`
- **`database/`** — Dual database layer:
  - **SQLAlchemy** (user settings): `base.py`, `engine.py`, `session.py`, `models/user_setting.py` — `UserSetting` model with `auto_fetch_in_dm` and `force_refresh_cache` toggles. Supports SQLite (dev) and PostgreSQL (prod) via `SETTINGS_DATABASE_URL`. Alembic migrations in `packages/shared/alembic/`
  - **`database/mongodb/`** — Beanie ODM for scraped content persistence, shared across API and async worker:
    - **`connection.py`** — `init_mongodb(mongodb_url, db_name)`, `close_mongodb()`, `save_instances()`. Parameterized — each app passes its own config at startup
    - **`cache.py`** — MongoDB-backed URL cache: `find_cached(url, ttl_seconds)` returns the latest versioned document if within TTL (0 = never expire); `save_metadata(metadata_item)` auto-increments `version` for the same URL before inserting
    - **`models/metadata.py`** — `Metadata(Document)` with fields: title, url, author, content, media_files, telegraph_url, timestamp, version, etc. `DatabaseMediaFile(MediaFile)` extends the scraper `MediaFile` dataclass with `file_key` for S3 storage and inherits `telegram_file_id` for Telegram file_id caching. Compound index on `(url, version)` for efficient cache lookups. `@before_event(Insert)` hook auto-computes text lengths and converts `MediaFile` → `DatabaseMediaFile`. Custom `bson_encoders = {DatabaseMediaFile: asdict}` ensures proper BSON serialization of pydantic dataclasses
    - **`__init__.py`** — Re-exports: `init_mongodb`, `close_mongodb`, `save_instances`, `find_cached`, `save_metadata`, `Metadata`, `DatabaseMediaFile`
- **`services/scrapers/`** — All platform scrapers, fully decoupled from FastAPI:
  - **`config.py`** — All scraper env vars: platform credentials (Twitter, Bluesky, Weibo, XHS, Zhihu, Reddit, Instagram), Firecrawl/Zyte config, OpenAI key, Telegraph tokens, `JINJA2_ENV`, cookie file loading. Configurable `CONF_DIR` for cookie/config files
  - **`common.py`** — Core `InfoExtractService`: routes URLs to the correct scraper, returns raw metadata. Includes MongoDB cache lookup at the top of `get_item()` when `store_database=True` and `database_cache_ttl >= 0`. Cache hits return a dict with `_cached=True` so callers can skip enrichment. Uses lazy imports for `find_cached` to avoid import-time beanie dependency
  - **`scraper.py`** — Base `Scraper` and `DataProcessor` abstract classes
  - **`scraper_manager.py`** — `ScraperManager` with lazy initialization for bluesky, weibo, and general scrapers
  - **`templates/`** — 13 Jinja2 templates for platform-specific output formatting (bundled via `__file__`-relative paths)
  - **Platform modules**: `twitter/`, `bluesky/`, `weibo/`, `xiaohongshu/`, `reddit/`, `instagram/`, `zhihu/`, `douban/`, `threads/`, `wechat/`, `general/` (Firecrawl + Zyte)
- **`services/telegraph/`** — Telegraph content publishing (creates telegra.ph pages from scraped content)
- **`services/file_export/`** — Async Celery task wrappers for PDF export, video download, and audio transcription. These accept `celery_app` and `timeout` as constructor parameters (dependency injection) so any app can use them with its own Celery client

The shared scrapers library can be used standalone without the API server:
```python
from fastfetchbot_shared.services.scrapers import InfoExtractService, ScraperManager
```

Optional dependencies are grouped under `fastfetchbot-shared[scrapers]` (Jinja2, atproto, asyncpraw, firecrawl-py, etc.) and `fastfetchbot-shared[mongodb]` (beanie, motor).

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

**MongoDB** (scraped content — optional, feature-gated):
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_ON` | `false` | Enable MongoDB storage of scraped metadata |
| `DATABASE_CACHE_TTL` | `86400` | Cache TTL in seconds. `0` = never expire (always use cache) |
| `MONGODB_HOST` | `localhost` | MongoDB host |
| `MONGODB_PORT` | `27017` | MongoDB port |
| `MONGODB_USERNAME` | `""` | MongoDB username (async worker only; included in derived URL if set) |
| `MONGODB_PASSWORD` | `""` | MongoDB password (async worker only) |
| `MONGODB_URL` | derived | Full MongoDB URI. Overrides host/port/credentials if set explicitly |

MongoDB models and connection logic live in `packages/shared/fastfetchbot_shared/database/mongodb/`. Both the API server and async worker use the same shared ODM layer. The `Metadata` Beanie Document stores scraped content with versioning — each re-scrape of the same URL increments the `version` field. The cache system (`find_cached` / `save_metadata`) queries the latest version and checks TTL before deciding to re-scrape.

**Telegram file_id caching** — automatic when `DATABASE_ON` is true and `SCRAPE_MODE` is `queue`:
- When the bot sends media to users, it extracts Telegram `file_id` values from the `send_media_group` response
- File_ids are pushed to Redis queue `fileid:updates` via the bot's `file_id_capture` module (fire-and-forget background task)
- The async worker's `file_id_consumer` processes the queue and persists file_ids to the corresponding `Metadata.media_files[*].telegram_file_id` in MongoDB
- On subsequent cache hits, `media_files_packaging` uses stored file_ids directly via `InputMediaPhoto(file_id)` etc., skipping HTTP download entirely
- The bot has no direct MongoDB access — all database writes go through the async worker via Redis

**SQLite/PostgreSQL** (user settings — always enabled for the Telegram bot):
| Variable | Default | Description |
|----------|---------|-------------|
| `SETTINGS_DATABASE_URL` | `sqlite+aiosqlite:///data/fastfetchbot.db` | SQLAlchemy connection URL. Use `postgresql+asyncpg://...` for production |

Alembic migrations live in `packages/shared/alembic/`. Run with:
```bash
cd packages/shared
SETTINGS_DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" uv run alembic upgrade head
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) builds and pushes all four images on push to `main`:
- `ghcr.io/aturret/fastfetchbot-api:latest`
- `ghcr.io/aturret/fastfetchbot-tgbot:latest`
- `ghcr.io/aturret/fastfetchbot-worker:latest`
- `ghcr.io/aturret/fastfetchbot-async-worker:latest`

## Development Guidelines

### Adding a New Platform Scraper
1. Create scraper module in `packages/shared/fastfetchbot_shared/services/scrapers/<platform>/`
2. Implement scraper class following existing patterns (extend `Scraper`/`DataProcessor` from `scraper.py`)
3. Add platform credentials to `packages/shared/fastfetchbot_shared/services/scrapers/config.py`
4. Register the scraper in `InfoExtractService.service_classes` (in `common.py`) or `ScraperManager` (for scrapers needing lazy init)
5. Add Jinja2 templates to `packages/shared/fastfetchbot_shared/services/scrapers/templates/`
6. Add platform-specific router in `apps/api/src/routers/` (if API endpoints are needed)
7. Add any new pip dependencies to `packages/shared/pyproject.toml` under `[project.optional-dependencies] scrapers`

### Exception Handling
- **Custom exceptions** are defined in `packages/shared/fastfetchbot_shared/exceptions.py`:
  - `FastFetchBotError` — base for all domain errors
  - `ScraperError` / `ScraperNetworkError` / `ScraperParseError` — scraper failures
  - `TelegraphPublishError` — Telegraph publishing failures
  - `FileExportError` — file export (PDF, video, audio) failures
  - `ExternalServiceError` — external service call failures (OpenAI, Firecrawl, Zyte, XHS sign server, etc.)
- **Always use typed exceptions** instead of generic `RuntimeError`, `ValueError`, or `Exception` for domain errors. Pick the most specific subclass that fits.
- **Use `from e` chaining** when wrapping exceptions: `raise ScraperError("message") from e`
- **Boundary-level handlers** catch exceptions at service boundaries:
  - FastAPI: global `@app.exception_handler(FastFetchBotError)` returns 502, generic `Exception` returns 500
  - Telegram bot: `error_process` handler catches handler exceptions; webhook server protects endpoints
  - Celery/ARQ workers: existing task-level try/catch with outbox error push
- **Never use `print()` or `traceback.print_exc()`** — always use `logger.exception()` (includes traceback) or `logger.error()` (message only)
- **Never silently swallow exceptions** — if catching an exception, either re-raise it or handle it explicitly with logging. Do not return `None` or empty data on failure.
- **Fail fast after fallback chains** — scrapers may try multiple methods/APIs, but must raise a typed error when all fallbacks are exhausted

### Key Conventions
- **`packages/shared/` (`fastfetchbot-shared`)** is for shared async logic — scrapers, templates, Telegraph, and async Celery task wrappers (file_export). Most code here is async and reusable across apps
- **`packages/file-export/` (`fastfetchbot-file-export`)** is exclusively for synchronous Celery worker jobs — the heavy I/O operations that run inside the Celery worker process (yt-dlp video download, WeasyPrint PDF generation, OpenAI audio transcription). Apps never import this package directly; they use the async wrappers in `fastfetchbot_shared.services.file_export` which submit tasks to the Celery worker
- **Scrapers, templates, and Telegraph live in `packages/shared/`** — they are framework-agnostic and reusable
- Scraper config (platform credentials, Firecrawl/Zyte settings) lives in `fastfetchbot_shared.services.scrapers.config`, **not** in `apps/api/src/config.py`
- API-only config (BASE_URL, MongoDB, Celery, AWS, Inoreader) stays in `apps/api/src/config.py`
- The API's `InfoExtractService` (in `apps/api/src/services/scrapers/common.py`) extends the shared core to add Telegraph, PDF, DB, and video enrichment
- API `services/telegraph/` is a re-export wrapper — the real implementation is in shared
- Telegram bot code goes in `apps/telegram-bot/core/`
- The bot communicates with the API only via HTTP — no direct imports of API code
- Jinja2 templates for output formatting, with i18n support via Babel
- Loguru for logging, Sentry for production error monitoring
- Store sensitive cookies/tokens in environment variables, never in code
