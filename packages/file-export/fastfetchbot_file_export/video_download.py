import os
import traceback

from loguru import logger
from yt_dlp import YoutubeDL


def get_video_orientation(content_info: dict, extractor: str) -> str:
    """Detect if video is vertical or horizontal. Only applies to YouTube."""
    if extractor != "youtube":
        return "horizontal"

    if not content_info.get("formats"):
        return "vertical"
    one_video_info = content_info["formats"][0]
    if one_video_info.get("aspect_ratio", 0.56) < 1:
        return "vertical"
    return "horizontal"


def get_format_for_orientation(
    extractor: str, orientation: str, hd: bool, bilibili_cookie: bool = False
) -> str:
    """Return appropriate yt-dlp format string based on video orientation."""
    if extractor == "youtube":
        if orientation == "vertical":
            return "bv[ext=mp4]+ba/b"
        else:
            return (
                "bv[ext=mp4]+(258/256/140)/best"
                if hd
                else "bv+ba/b"
            )
    elif extractor == "bilibili":
        if hd and bilibili_cookie:
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        return "bv*[height<=480]+ba/b[height<=480] / wv*+ba/w"
    raise ValueError("no available extractor found")


def init_yt_downloader(
    hd: bool = False,
    audio_only: bool = False,
    extractor: str = None,
    no_proxy: bool = False,
    extract_only: bool = False,
    video_format: str = None,
    download_dir: str = "/tmp",
    cookie_file_path: str = None,
    proxy_mode: bool = False,
    proxy_url: str = "",
    youtube_cookie: bool = False,
    bilibili_cookie: bool = False,
) -> YoutubeDL:
    """Initialize a YoutubeDL instance with the given configuration."""
    base_opts = {"merge_output_format": "mp4"}

    if extract_only:
        ydl_opts = {
            **base_opts,
            "ignore_no_formats_error": True,
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "allow_unplayable_formats": True,
        }
    elif audio_only:
        ydl_opts = {
            **base_opts,
            "paths": {"home": download_dir},
            "format": "m4a/bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
            ],
        }
    else:
        if video_format is None:
            if extractor is None:
                raise ValueError("extractor cannot be None")
            elif extractor == "youtube":
                video_format = (
                    "bv[ext=mp4]+(258/256/140)/best"
                    if hd
                    else "bv+ba/b"
                )
            elif extractor == "bilibili":
                if hd and bilibili_cookie:
                    video_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                else:
                    video_format = "bv*[height<=480]+ba/b[height<=480] / wv*+ba/w"
            else:
                raise ValueError("no available extractor found")

        ydl_opts = {
            **base_opts,
            "paths": {"home": download_dir},
            "outtmpl": {"default": "%(title).10s-%(id)s.%(ext)s"},
            "format": video_format,
            "referer": "https://www.bilibili.com/",
        }

    if youtube_cookie and extractor == "youtube" and cookie_file_path:
        logger.info("Using cookies for youtube")
        ydl_opts["cookiefile"] = cookie_file_path

    if bilibili_cookie and extractor == "bilibili" and cookie_file_path:
        logger.info("Using cookies for bilibili")
        ydl_opts["cookiefile"] = cookie_file_path

    if proxy_mode and not no_proxy:
        logger.info("Using proxy")
        ydl_opts["proxy"] = proxy_url

    downloader = YoutubeDL(ydl_opts)
    return downloader


def download_video(
    url: str,
    download: bool = True,
    hd: bool = False,
    extractor: str = "youtube",
    audio_only: bool = False,
    config: dict = None,
) -> dict:
    """
    Download or extract info for a video.

    config keys: DOWNLOAD_DIR, COOKIE_FILE_PATH, PROXY_MODE, PROXY_URL,
                 YOUTUBE_COOKIE, BILIBILI_COOKIE, LOCAL_MODE, BASE_URL
    """
    if config is None:
        config = {}

    download_dir = config.get("DOWNLOAD_DIR", "/tmp")
    cookie_file_path = config.get("COOKIE_FILE_PATH", "")
    proxy_mode = config.get("PROXY_MODE", False)
    proxy_url = config.get("PROXY_URL", "")
    youtube_cookie = config.get("YOUTUBE_COOKIE", False)
    bilibili_cookie = config.get("BILIBILI_COOKIE", False)
    local_mode = config.get("LOCAL_MODE", True)
    base_url = config.get("BASE_URL", "")

    file_path_output = None

    try:
        # Phase 1: Extract info only (no downloading)
        with init_yt_downloader(
            extractor=extractor,
            extract_only=True,
            download_dir=download_dir,
            cookie_file_path=cookie_file_path,
            proxy_mode=proxy_mode,
            proxy_url=proxy_url,
            youtube_cookie=youtube_cookie,
            bilibili_cookie=bilibili_cookie,
        ) as extractor_dl:
            content_info = extractor_dl.extract_info(url, download=False)

        # Determine video orientation
        orientation = get_video_orientation(content_info, extractor)
        logger.info(f"Video orientation: {orientation}")

        # Phase 2: Download with appropriate format based on orientation
        if download:
            if audio_only:
                downloader = init_yt_downloader(
                    audio_only=True,
                    extractor=extractor,
                    download_dir=download_dir,
                    cookie_file_path=cookie_file_path,
                    proxy_mode=proxy_mode,
                    proxy_url=proxy_url,
                    youtube_cookie=youtube_cookie,
                    bilibili_cookie=bilibili_cookie,
                )
            else:
                video_format = get_format_for_orientation(
                    extractor, orientation, hd, bilibili_cookie
                )
                downloader = init_yt_downloader(
                    extractor=extractor,
                    video_format=video_format,
                    download_dir=download_dir,
                    cookie_file_path=cookie_file_path,
                    proxy_mode=proxy_mode,
                    proxy_url=proxy_url,
                    youtube_cookie=youtube_cookie,
                    bilibili_cookie=bilibili_cookie,
                )

            with downloader:
                downloader.download([url])
                file_path = downloader.prepare_filename(content_info)
                file_path_output = (
                    file_path
                    if local_mode
                    else base_url + "/fileDownload" + file_path
                )

        return {
            "message": "success",
            "content_info": content_info,
            "orientation": orientation,
            "file_path": file_path_output,
        }
    except Exception as e:
        traceback.print_exc()
        raise
