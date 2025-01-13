Demo: https://t.me/aturretrss_bot

# FastFetchBot

A social media fetch API based on [FastAPI](https://fastapi.tiangolo.com/), with Telegram Bot as the default client.

Supported most mainstream social media platforms. You can get a permanent copy of the content by just sending the url to the bot.

Other separated microservices for this project:

- [FastFileExporter](https://github.com/aturret/FastFileExporter)
- [FastFetchBot-Telegram-Bot](https://github.com/aturret/FastFetchBot-Telegram-Bot)


## Installation

### Docker (Recommended)

Download the docker-compose.yml file and set the environment variables as the following section.

#### Env

Create a `.env` file at the same directory and set the [environment variables](#envrionment-variables).

#### Local Telegram API Sever

If you want to send documents that larger than 50MB, you need to run a local telegram api server. The `docker-compose.yml` file has already give you an example. You just need to fill the `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in the yml file. If you don't need it, just comment it out.

```bash
docker-compose up -d
```

### Python (Not Recommended)

Local Telegram API sever and video download function is not supported in this way. If you do really need these functions, you can run the telegram api server and [the file export server](https://github.com/aturret/FastFileExporter) manually.

We use [Poetry](https://python-poetry.org/) as the package manager for this project. You can install it by the following command.

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

## Environment Variables

Note: Many of the services requires cookies to fetch content. You can get your cookies by browser extension [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) and set the cookies as environment variables.


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

Must set cookies variables if you want to fetch twitter content.

- `TWITTER_CT0`: The ct0 cookie of twitter. Default: `None`
- `TWITTER_AUTH_TOKEN`: The auth token of twitter. Default: `None`

#### Reddit

We use `read_only` mode of `praw` to fetch reddit content. We still need to set the `client_id` , `client_secret` , `username` and `password` of your reddit api account.

- `REDDIT_CLIENT_ID`: The client id of reddit. Default: `None`
- `REDDIT_CLIENT_SECRET`: The client secret of reddit. Default: `None`
- `REDDIT_USERNAME`: The username of reddit. Default: `None`
- `REDDIT_PASSWORD`: The password of reddit. Default: `None`

#### Weibo

- `WEIBO_COOKIES`: The cookie of weibo. For some unknown reasons, some weibo posts may be not accessible if you don't are not logged in. Just copy the cookie from your browser and set it. Default: `None`

#### Xiaohongshu

- `XIAOHONGSHU_A1`: The a1 cookie of xiaohongshu. Default: `None`
- `XIAOHONGSHU_WEBID`: The webid cookie of xiaohongshu. Default: `None`
- `XIAOHONGSHU_WEBSESSION`: The websession cookie of xiaohongshu. Default: `None`
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

### Video Content

- [x] Youtube
- [x] Bilibili

## Acknowledgements

The HTML to Telegra.ph converter function is based on [html-telegraph-poster](https://github.com/mercuree/html-telegraph-poster). I separated it from this project as an independent Python package: [html-telegraph-poster-v2](https://github.com/aturret/html-telegraph-poster-v2).

The Xiaohongshu scraper is based on [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler).

The Weibo scraper is based on [weiboSpider](https://github.com/dataabc/weiboSpider).

The Twitter scraper is based on [twitter-api-client](https://github.com/trevorhobenshield/twitter-api-client).

The Zhihu scraper is based on [fxzhihu](https://github.com/frostming/fxzhihu).

All the code is licensed under the MIT license. I either used their code as-is or made modifications to implement certain functions. I want to express my gratitude to the projects mentioned above for their contributions.
