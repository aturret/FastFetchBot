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
from fastfetchbot_shared.utils.logger import logger

# Union of fields used by _youtube_info_parse and _bilibili_info_parse
_CONTENT_INFO_FIELDS = (
    "id", "title", "uploader", "uploader_url", "uploader_id", "channel_url",
    "description", "view_count", "comment_count", "like_count",
    "thumbnail", "upload_date", "timestamp", "duration", "ext",
)


def _sanitize_content_info(content_info: dict) -> dict:
    """Extract only the fields the API consumer needs from the full yt-dlp dict.

    The raw yt-dlp content_info contains 100+ fields (including a formats array
    with 20-50+ objects). The API only uses ~15 metadata fields plus
    formats[0].aspect_ratio for orientation detection.
    """
    sanitized = {k: content_info.get(k) for k in _CONTENT_INFO_FIELDS}
    # Preserve only the first format's aspect_ratio (used by get_video_orientation)
    formats = content_info.get("formats")
    if formats and len(formats) > 0:
        sanitized["formats"] = [{"aspect_ratio": formats[0].get("aspect_ratio")}]
    else:
        sanitized["formats"] = []
    return sanitized


@app.task(name="file_export.video_download")
def video_download_task(
    url: str,
    download: bool = True,
    hd: bool = False,
    extractor: str = "youtube",
    audio_only: bool = False,
) -> dict:
    logger.info(f"video_download_task started: url={url}, extractor={extractor}, download={download}, hd={hd}, audio_only={audio_only}")
    config = {
        "DOWNLOAD_DIR": DOWNLOAD_DIR,
        "COOKIE_FILE_PATH": COOKIE_FILE_PATH,
        "PROXY_MODE": PROXY_MODE,
        "PROXY_URL": PROXY_URL,
        "YOUTUBE_COOKIE": YOUTUBE_COOKIE,
        "BILIBILI_COOKIE": BILIBILI_COOKIE,
        "LOCAL_MODE": True,
    }
    try:
        result = download_video(
            url=url,
            download=download,
            hd=hd,
            extractor=extractor,
            audio_only=audio_only,
            config=config,
        )
    except Exception:
        logger.exception(f"video_download_task failed: url={url}, extractor={extractor}")
        raise
    result["content_info"] = _sanitize_content_info(result["content_info"])
    logger.info(f"video_download_task completed: url={url}, file_path={result.get('file_path')}")
    return result
