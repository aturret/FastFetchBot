import sentry_sdk

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware

from src import database
from src.routers import inoreader, scraper_routers, scraper
from src.config import DATABASE_ON
from fastfetchbot_shared.utils.logger import logger

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
    if DATABASE_ON:
        await database.startup()
    try:
        yield
    finally:
        if DATABASE_ON:
            await database.shutdown()


class LogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        logger.info(f"{request.method} {request.url}")
        response = await call_next(request)
        return response


def create_app():
    fastapi_app = FastAPI(lifespan=lifespan)
    fastapi_app.add_middleware(LogMiddleware)
    fastapi_app.include_router(inoreader.router)
    fastapi_app.include_router(scraper.router)
    for router in scraper_routers.scraper_routers:
        fastapi_app.include_router(router)
    return fastapi_app


app = create_app()
