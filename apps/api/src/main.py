import sentry_sdk

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware

from src import database
from src.routers import inoreader, scraper_routers, scraper
from src.config import settings
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.exceptions import FastFetchBotError

SENTRY_DSN = ""

# https://docs.sentry.io/platforms/python/guides/fastapi/
sentry_sdk.init(
    dsn=SENTRY_DSN,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production,
    traces_sample_rate=1.0,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DATABASE_ON:
        await database.startup()
    try:
        yield
    finally:
        if settings.DATABASE_ON:
            await database.shutdown()


class LogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        logger.info(f"{request.method} {request.url}")
        try:
            response = await call_next(request)
            return response
        except Exception:
            logger.exception(f"Unhandled error during {request.method} {request.url}")
            raise


def create_app():
    fastapi_app = FastAPI(lifespan=lifespan)

    @fastapi_app.exception_handler(FastFetchBotError)
    async def fastfetchbot_error_handler(request: Request, exc: FastFetchBotError):
        logger.error(f"Domain error on {request.method} {request.url}: {exc}")
        return JSONResponse(status_code=502, content={"error": str(exc)})

    @fastapi_app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error on {request.method} {request.url}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    fastapi_app.add_middleware(LogMiddleware)
    fastapi_app.include_router(inoreader.router)
    fastapi_app.include_router(scraper.router)
    for router in scraper_routers.scraper_routers:
        fastapi_app.include_router(router)
    return fastapi_app


app = create_app()
