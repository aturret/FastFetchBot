from worker_core.main import app
from worker_core.config import (
    DOWNLOAD_DIR,
    COOKIE_FILE_PATH,
    PROXY_MODE,
    PROXY_URL,
    YOUTUBE_COOKIE,
    BILIBILI_COOKIE,
)
from fastfetchbot_file_export.video_download import download_video


@app.task(name="file_export.video_download")
def video_download_task(
    url: str,
    download: bool = True,
    hd: bool = False,
    extractor: str = "youtube",
    audio_only: bool = False,
) -> dict:
    config = {
        "DOWNLOAD_DIR": DOWNLOAD_DIR,
        "COOKIE_FILE_PATH": COOKIE_FILE_PATH,
        "PROXY_MODE": PROXY_MODE,
        "PROXY_URL": PROXY_URL,
        "YOUTUBE_COOKIE": YOUTUBE_COOKIE,
        "BILIBILI_COOKIE": BILIBILI_COOKIE,
        "LOCAL_MODE": True,
    }
    return download_video(
        url=url,
        download=download,
        hd=hd,
        extractor=extractor,
        audio_only=audio_only,
        config=config,
    )
