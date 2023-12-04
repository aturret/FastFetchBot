import secrets

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyQuery, APIKeyHeader

from app.config import API_KEY_NAME, API_KEY, TELEGRAM_BOT_SECRET_TOKEN

api_key_query = APIKeyQuery(name=API_KEY_NAME, auto_error=False)
telegram_secret_token_query = APIKeyHeader(
    name="X-Telegram-Bot-Api-Secret-Token", auto_error=False
)


def verify_key(input_key: str, true_key: str):
    if api_key_query is None or not secrets.compare_digest(input_key, true_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key Invalid"
        )


def verify_api_key(api_key_query: str = Security(api_key_query)):
    verify_key(api_key_query, API_KEY)


def verify_telegram_api_header(
    api_header_query: str = Security(telegram_secret_token_query),
):
    if api_header_query is None or not secrets.compare_digest(
        api_header_query, TELEGRAM_BOT_SECRET_TOKEN
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key Invalid"
        )
