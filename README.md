Demo: https://t.me/aturretrss_bot

# FastFetchBot

A social media content fetching service with a Telegram Bot client, built as a monorepo with two microservices.

Send a social media URL to the bot, and it fetches and archives the content for you. Supports most mainstream social media platforms.

## Architecture

FastFetchBot is organized as a UV workspace monorepo with three packages:

```
FastFetchBot/
├── packages/shared/          # fastfetchbot-shared: common models, utilities, logger
├── apps/api/                 # FastAPI server: scrapers, storage, routing
├── apps/telegram-bot/        # Telegram Bot: webhook/polling, message handling
├── app/                      # Legacy re-export wrappers (backward compatibility)
├── pyproject.toml            # Root workspace configuration
└── uv.lock                   # Lockfile for the entire workspace
```

| Service | Port | Description |
|---------|------|-------------|
| **API Server** (`apps/api/`) | 10450 | FastAPI app with all platform scrapers, file export, and storage |
| **Telegram Bot** (`apps/telegram-bot/`) | 10451 | Receives messages via webhook or long polling, calls the API server |

The Telegram Bot communicates with the API server over HTTP. In Docker, this is `http://api:10450`.

## Installation

### Docker (Recommended)

1. Copy `docker-compose.template.yml` to `docker-compose.yml`.
2. Create a `.env` file from `template.env` and fill in the [environment variables](#environment-variables).
3. If you need large file support (>50 MB), fill in `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in the compose file for the local Telegram Bot API server. Otherwise, comment out the `telegram-bot-api` service.

```bash
docker-compose up -d
```

The compose file pulls pre-built images from GitHub Container Registry:

- `ghcr.io/aturret/fastfetchbot-api:latest`
- `ghcr.io/aturret/fastfetchbot-telegram-bot:latest`

To build locally instead, uncomment the `build:` blocks and comment out the `image:` lines in `docker-compose.yml`.

### Local Development

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
# Install all dependencies (including dev)
uv sync

# Run the API server
cd apps/api
uv run gunicorn -k uvicorn.workers.UvicornWorker src.main:app --preload

# Run the Telegram Bot (in a separate terminal)
cd apps/telegram-bot
uv run python -m core.main
```

### Telegram Bot Modes

The bot supports two modes, controlled by the `TELEGRAM_BOT_MODE` environment variable:

| Mode | Value | Use Case |
|------|-------|----------|
| **Long Polling** | `polling` (default) | Local development, simple deployments without a reverse proxy |
| **Webhook** | `webhook` | Production with a public HTTPS URL |

In both modes, the bot runs an HTTP server on port 10451 for the `/send_message` callback endpoint (used by Inoreader integration) and `/health`.

## Development

### Commands

```bash
uv sync                    # Install all dependencies
uv run pytest              # Run tests
uv run pytest -v           # Run tests with verbose output
uv run black .             # Format code
```

### Adding a New Platform Scraper

1. Create a new scraper module in `apps/api/src/services/scrapers/<platform>/`
2. Implement the scraper class following existing patterns
3. Add a platform-specific router in `apps/api/src/routers/`
4. Register the scraper in `ScraperManager`
5. Add configuration variables in `apps/api/src/config.py`
6. Create tests in `tests/cases/`

### Docker Build

```bash
# Build both services locally
docker-compose build

# Or build individually
docker build -f apps/api/Dockerfile -t fastfetchbot-api .
docker build -f apps/telegram-bot/Dockerfile -t fastfetchbot-telegram-bot .
```

> **Note:** Both Dockerfiles use the repository root as the build context (`.`) because they need access to `pyproject.toml`, `uv.lock`, and `packages/shared/`.

## Environment Variables

Many scrapers require authentication cookies. You can extract cookies using the browser extension [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).

See `template.env` for a complete reference with comments.

### Required

| Variable | Description |
|----------|-------------|
| `BASE_URL` | Public domain of the server (e.g. `example.com`). Used for webhook URL construction. |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Default chat ID for the bot |

### Service Communication (Docker)

| Variable | Default | Description |
|----------|---------|-------------|
| `API_SERVER_URL` | `http://localhost:10450` | URL the Telegram Bot uses to call the API server. Set to `http://api:10450` in Docker. |
| `TELEGRAM_BOT_CALLBACK_URL` | `http://localhost:10451` | URL the API server uses to call the Telegram Bot. Set to `http://telegram-bot:10451` in Docker. |
| `TELEGRAM_BOT_MODE` | `polling` | `polling` or `webhook` |

### Optional

#### API Server

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `10450` | API server port |
| `API_KEY` | auto-generated | API key for authentication |

#### Telegram

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEBOT_API_SERVER_HOST` | `None` | Local Telegram Bot API server host |
| `TELEBOT_API_SERVER_PORT` | `None` | Local Telegram Bot API server port |
| `TELEGRAM_CHANNEL_ID` | `None` | Channel ID(s) for the bot, comma-separated |
| `TELEGRAM_CHANNEL_ADMIN_LIST` | `None` | User IDs allowed to post to the channel, comma-separated |

#### Platform Cookies & Credentials

| Platform | Variables |
|----------|-----------|
| Twitter | `TWITTER_CT0`, `TWITTER_AUTH_TOKEN` |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD` |
| Weibo | `WEIBO_COOKIES` |
| Xiaohongshu | `XIAOHONGSHU_A1`, `XIAOHONGSHU_WEBID`, `XIAOHONGSHU_WEBSESSION` |
| Instagram | `X_RAPIDAPI_KEY` |
| Zhihu | Store cookies in `conf/zhihu_cookies.json` |

#### Cloud Services

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for audio transcription |
| `AWS_ACCESS_KEY_ID` | Amazon S3 access key |
| `AWS_SECRET_ACCESS_KEY` | Amazon S3 secret key |
| `AWS_S3_BUCKET_NAME` | S3 bucket name |
| `AWS_S3_REGION_NAME` | S3 region |
| `AWS_DOMAIN_HOST` | Custom domain bound to the S3 bucket |

#### General Webpage Scraping

| Variable | Default | Description |
|----------|---------|-------------|
| `GENERAL_SCRAPING_ON` | `false` | Enable scraping for unrecognized URLs |
| `GENERAL_SCRAPING_API` | `FIRECRAWL` | Backend: `FIRECRAWL` or `ZYTE` |
| `FIRECRAWL_API_URL` | | Firecrawl API server URL |
| `FIRECRAWL_API_KEY` | | Firecrawl API key |
| `ZYTE_API_KEY` | | Zyte API key |

## Supported Content Types

### Social Media

- [x] Twitter
- [x] Bluesky (Beta, only supports part of posts)
- [x] Instagram
- [ ] Threads
- [x] Reddit (Beta, only supports part of posts)
- [ ] Quora
- [x] Weibo
- [x] WeChat Public Account Articles
- [x] Zhihu
- [x] Douban
- [ ] Xiaohongshu

### Video

- [x] YouTube
- [x] Bilibili

## CI/CD

The GitHub Actions pipeline (`.github/workflows/ci.yml`) automatically builds and pushes both microservice images to GitHub Container Registry on every push to `main`:

- `ghcr.io/aturret/fastfetchbot-api:latest`
- `ghcr.io/aturret/fastfetchbot-telegram-bot:latest`

## Acknowledgements

The HTML to Telegra.ph converter function is based on [html-telegraph-poster](https://github.com/mercuree/html-telegraph-poster). I separated it from this project as an independent Python package: [html-telegraph-poster-v2](https://github.com/aturret/html-telegraph-poster-v2).

The Xiaohongshu scraper is based on [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler).

The Weibo scraper is based on [weiboSpider](https://github.com/dataabc/weiboSpider).

The Twitter scraper is based on [twitter-api-client](https://github.com/trevorhobenshield/twitter-api-client).

The Zhihu scraper is based on [fxzhihu](https://github.com/frostming/fxzhihu).

All the code is licensed under the MIT license. I either used their code as-is or made modifications to implement certain functions. I want to express my gratitude to the projects mentioned above for their contributions.
