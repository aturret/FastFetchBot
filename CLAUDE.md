# CLAUDE.md

## Project Overview

FastFetchBot is a social media content fetching API built with FastAPI, designed to scrape and archive content from various social media platforms. It includes a Telegram Bot as the default client interface and supports multiple social media platforms including Twitter, Weibo, Xiaohongshu, Reddit, Bluesky, Instagram, Zhihu, Douban, YouTube, and Bilibili.

## Development Commands

### Package Management
- `uv sync` - Install all dependencies (including dev)
- `uv sync --no-dev` - Install production dependencies only
- `uv sync --extra windows` - Install with Windows extras
- `uv lock` - Regenerate the lock file after pyproject.toml changes

### Running the Application
- **Production**: `uv run gunicorn -k uvicorn.workers.UvicornWorker app.main:app --preload`
- **Development**: `uv run gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:10450 wsgi:app`

### Docker Commands
- `docker-compose up -d` - Start all services (FastFetchBot, Telegram Bot API, File Exporter)
- `docker-compose build` - Build the FastFetchBot container

### Testing
- `uv run pytest` - Run all tests
- `uv run pytest tests/test_bluesky.py` - Run specific test file
- `uv run pytest -v` - Run tests with verbose output

### Code Formatting
- `uv run black .` - Format all Python code using Black formatter

## Architecture Overview

### Core Components

**FastAPI Application (`app/main.py`)**
- Main application entry point with FastAPI instance
- Configures routers, middleware, and lifecycle management
- Integrates Sentry for error monitoring
- Handles Telegram bot webhook setup on startup

**Scraper Architecture (`app/services/scrapers/`)**
- `ScraperManager`: Centralized manager for all platform scrapers
- Individual scraper modules for each platform (twitter, weibo, bluesky, etc.)
- Each scraper implements platform-specific content extraction logic
- Common scraping utilities in `common.py`

**Router Structure (`app/routers/`)**
- Platform-specific routers (twitter.py, weibo.py, etc.)
- Generic scraper router for unified API endpoints
- Telegram bot webhook handler
- Feed processing and Inoreader integration

**Data Models (`app/models/`)**
- `classes.py`: Core data structures (NamedBytesIO)
- `database_model.py`: MongoDB/Beanie models
- Platform-specific metadata models
- Telegram chat and Telegraph item models

**Configuration (`app/config.py`)**
- Comprehensive environment variable handling
- Platform-specific API credentials and cookies
- Database, storage, and service configurations
- Template and localization settings

### Key Services

**Telegram Bot Service (`app/services/telegram_bot/`)**
- Handles webhook setup and message processing
- Integrates with local Telegram Bot API server for large file support
- Channel and admin management

**File Export Service (`app/services/file_export/`)**
- Document export (PDF generation)
- Audio transcription (OpenAI integration)
- Video download capabilities

**Storage Services**
- Amazon S3 integration for media storage
- Local file system management
- Telegraph integration for content publishing

### Platform Support

**Supported Social Media Platforms:**
- Twitter (requires ct0 and auth_token cookies)
- Weibo (requires cookies)
- Xiaohongshu (requires a1, webid, websession cookies)
- Bluesky (requires username/password)
- Reddit (requires API credentials)
- Instagram (requires X-RapidAPI key)
- Zhihu (requires cookies in conf/zhihu_cookies.json)
- Douban
- YouTube, Bilibili (video content)

## Environment Configuration

### Required Variables
- `BASE_URL`: Server base URL
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_CHAT_ID`: Default chat ID for bot

### Critical Setup Notes
- Most social media scrapers require authentication cookies/tokens
- Use browser extension "Get cookies.txt LOCALLY" to extract cookies
- Store Zhihu cookies in `conf/zhihu_cookies.json`
- Template environment file available at `template.env`

### Database Integration
- Optional MongoDB integration (set `DATABASE_ON=true`)
- Uses Beanie ODM for async MongoDB operations
- Database initialization handled in app lifecycle

### Docker Services
- **fastfetchbot**: Main application container
- **telegram-bot-api**: Local Telegram Bot API for large file support
- **fast-yt-downloader**: Separate service for video downloads

## Development Guidelines

### Cookie Management
- Platform scrapers depend on valid authentication cookies
- Store sensitive cookies in environment variables, never in code
- Test scraper functionality after cookie updates

### Adding New Platform Support
1. Create new scraper module in `app/services/scrapers/[platform]/`
2. Implement scraper class following existing patterns
3. Add platform-specific router in `app/routers/`
4. Update ScraperManager to include new scraper
5. Add configuration variables in `app/config.py`
6. Create tests in `tests/cases/`

### Template System
- Jinja2 templates in `app/templates/` for content formatting
- Platform-specific templates for different output formats
- Supports internationalization via gettext

### Error Handling and Logging
- Loguru for comprehensive logging
- Sentry integration for production error monitoring
- Platform-specific error handling in scrapers