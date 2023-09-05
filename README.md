# FastFetchBot

A social media fetch bot based on [FastAPI](https://fastapi.tiangolo.com/).

Supported most mainstream social media platforms. You can get a permanent copy of the content by just sending the url to the bot.

## Installation

### Docker (Recommended)

Download the docker-compose.yml file, create a `.env` file at the same directory and set the environment variables.

```bash
docker-compose up -d
```

### Python

First, install the package manager [Poetry](https://python-poetry.org/).

```bash
pip install poetry
```

Then, install the dependencies.

```bash
poetry install
```

Finally, run the server.

```bash
poetry run gunicorn -k uvicorn.workers.UvicornWorker app.main:app --preload
```

## Envrionment Variables

### Required Variables

- `BASE_URL`: The base url of the server. example: `example.com`
- `TELEGRAM_BOT_TOKEN`: The token of the telegram bot.
- `TELEGRAM_CHAT_ID`: The chat id of the telegram bot.

### Optional Variables

#### FastAPI

- `PORT`: Default: `10450`
- `API_KEY`: The api key for the FastAPI server. It would be generated automatically if not set.

#### Telegram

- `TELEBOT_API_SERVER_HOST`: The host of the telegram bot api server. Default: `telegram-bot-api`
- `TELEBOT_API_SERVER_PORT`: The port of the telegram bot api server. Default: `8081`
- `TELEGRAM_CHANNEL_ID`: The channel id of the telegram bot. Default: `None`
- `TELEGRAM_CHANNEL_ADMIN_LIST`: The id list of the users who can send message to targeted telegram channel, divided by `,`. You cannot send message to the channel if you are not in the list. Default: `None`

#### Twitter

Must set if you want to fetch twitter content.

- `TWITTER_CT0`: The ct0 cookie of twitter. Default: `None`
- `TWITTER_AUTH_TOKEN`: The auth token of twitter. Default: `None`

#### OpenAI

You can set the api key of OpenAI to use the transcription function.

- `OPENAI_API_KEY`: The api key of OpenAI. Default: `None`

#### Amazon S3 Picture Storage

- `AWS_ACCESS_KEY_ID`: The access key id of Amazon S3. Default: `None`
- `AWS_SECRET_ACCESS_KEY`: The secret access key of Amazon S3. Default: `None`
- `AWS_S3_BUCKET_NAME`: The bucket name of Amazon S3. Default: `None`
- `AWS_S3_REGION_NAME`: The region name of Amazon S3. Default: `None`
- `AWS_DOMAIN_HOST`: The domain bound to the bucket. The picture upload function would generate images url by bucket name if customized host not set. Default: `None`

## Supported Content Types

### Social Media Content

- [x] Twitter
- [x] Instagram
- [x] Threads
- [ ] Quora
- [ ] Reddit


- [x] Weibo
- [x] WeChat Public Account Articles
- [x] Zhihu
- [x] Douban
- [ ] Xiaohongshu

### Video Content

- [x] Youtube
- [x] Bilibili