from loguru import logger
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from fastfetchbot_shared.exceptions import FileExportError
from fastfetchbot_file_export.bilibili_guest import GuestDownloadError, guest_download

BILIBILI_FORMAT_SORT = ("vcodec:h264",)

# (substrings to look for, case-insensitive) -> user-facing reason
_YTDLP_ERROR_REASONS = (
    (("http error 412", "precondition failed"), "B 站风控拦截，请稍后再试或配置 Cookie"),
    # yt-dlp's Bilibili extractor can't tell these apart (empty playinfo).
    (("deleted or geo-restricted",), "视频不存在、已删除或有地区限制"),
    (("requested format is not available",), "没有可用的视频格式"),
    (
        ("login", "log in", "sign in", "registered users", "premium", "大会员", "登录"),
        "需要登录或大会员",
    ),
    (("geo restrict", "geo-restrict", "in your country", "地区"), "地区限制"),
    (("http error 404", "video unavailable", "does not exist"), "视频不存在或已删除"),
)


def explain_ytdlp_error(exc: BaseException) -> str:
    """Map a yt-dlp failure to a short, user-facing reason."""
    text = str(exc)
    lowered = text.lower()
    for needles, reason in _YTDLP_ERROR_REASONS:
        if any(n in lowered for n in needles):
            return reason
    # yt-dlp messages look like "ERROR: \r[download] Got error: ..."; \r is not a line break here.
    text = text.replace("\r", " ").strip().removeprefix("ERROR:").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0][:200] if lines else type(exc).__name__


def _downloaded_file_path(downloader: YoutubeDL, info: dict) -> str:
    downloads = info.get("requested_downloads") or []
    if downloads and downloads[0].get("filepath"):
        return downloads[0]["filepath"]
    return info.get("filepath") or downloader.prepare_filename(info)


def get_video_orientation(content_info: dict, extractor: str) -> str:
    """Detect if video is vertical or horizontal. Only applies to YouTube."""
    if extractor != "youtube":
        return "horizontal"

    formats = content_info.get("formats")
    if not formats:
        return "horizontal"

    # Find the first video format (has aspect_ratio), skipping audio-only entries
    for fmt in formats:
        if "aspect_ratio" in fmt and fmt["aspect_ratio"] is not None:
            return "vertical" if fmt["aspect_ratio"] < 1 else "horizontal"

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
    raise FileExportError("no available extractor found")


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
            video_format = get_format_for_orientation(
                extractor, "horizontal", hd, bilibili_cookie
            )

        ydl_opts = {
            **base_opts,
            "paths": {"home": download_dir},
            "outtmpl": {"default": "%(title).10s-%(id)s.%(ext)s"},
            "format": video_format,
        }
        if extractor == "bilibili":
            ydl_opts["referer"] = "https://www.bilibili.com/"
            # Bilibili serves AVC, HEVC and AV1 all as mp4; prefer AVC so every
            # Telegram client can play the result. Other codecs remain fallbacks.
            ydl_opts["format_sort"] = list(BILIBILI_FORMAT_SORT)

    if extractor == "bilibili":
        # Multi-part videos are playlists to yt-dlp; fetch only the requested
        # part (?p=N, default the first) instead of every part.
        ydl_opts["noplaylist"] = True

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

    common = dict(
        extractor=extractor,
        download_dir=download_dir,
        cookie_file_path=cookie_file_path,
        proxy_mode=proxy_mode,
        proxy_url=proxy_url,
        youtube_cookie=youtube_cookie,
        bilibili_cookie=bilibili_cookie,
    )
    file_path_output = None

    try:
        # Only YouTube video downloads need the info up front (orientation picks
        # the format). Everything else is extracted exactly once.
        needs_probe = not download or (extractor == "youtube" and not audio_only)
        content_info = None
        if needs_probe:
            with init_yt_downloader(extract_only=True, **common) as extractor_dl:
                content_info = extractor_dl.extract_info(url, download=False)

        if download:
            if audio_only:
                downloader = init_yt_downloader(audio_only=True, **common)
            else:
                orientation = get_video_orientation(content_info or {}, extractor)
                video_format = get_format_for_orientation(
                    extractor, orientation, hd, bilibili_cookie
                )
                downloader = init_yt_downloader(video_format=video_format, **common)

            with downloader:
                if content_info is not None:
                    download_info = _download_with_info(downloader, content_info, url)
                else:
                    download_info = downloader.extract_info(url, download=True)
                    content_info = download_info
                file_path = _downloaded_file_path(downloader, download_info)
                file_path_output = (
                    file_path
                    if local_mode
                    else base_url + "/fileDownload" + file_path
                )

        orientation = get_video_orientation(content_info, extractor)
        logger.info(f"Video orientation: {orientation}")
        return {
            "message": "success",
            "content_info": content_info,
            "orientation": orientation,
            "file_path": file_path_output,
        }
    except Exception as e:
        logger.exception(f"download_video failed: url={url}")
        reason = explain_ytdlp_error(e)
        if not (extractor == "bilibili" and download and not audio_only):
            raise FileExportError(f"视频下载失败：{reason} ({url})") from e
        ytdlp_error, ytdlp_reason = e, reason

    # yt-dlp failed on a Bilibili video download: retry as a guest without yt-dlp.
    logger.warning(f"yt-dlp failed ({ytdlp_reason}), trying Bilibili guest download: url={url}")
    try:
        guest = guest_download(url, download_dir, proxy=proxy_url if proxy_mode else None)
    except GuestDownloadError as guest_error:
        logger.error(f"Bilibili guest download failed: {guest_error}")
        raise FileExportError(
            f"视频下载失败：{ytdlp_reason}；游客下载也失败：{guest_error} ({url})"
        ) from ytdlp_error
    except Exception as guest_error:
        logger.exception("Bilibili guest download crashed")
        raise FileExportError(
            f"视频下载失败：{ytdlp_reason}；游客下载也失败：{type(guest_error).__name__} ({url})"
        ) from ytdlp_error

    file_path = guest["file_path"]
    return {
        "message": "success",
        "content_info": guest["content_info"],
        "orientation": get_video_orientation(guest["content_info"], extractor),
        "file_path": file_path if local_mode else base_url + "/fileDownload" + file_path,
    }


def _download_with_info(downloader: YoutubeDL, content_info: dict, url: str) -> dict:
    """Download from already-extracted info, like yt-dlp's --load-info-json.

    The downloader re-runs format selection with its own options, so the probe's
    choice doesn't leak through. Expired media URLs fall back to a fresh extract.
    Playlists are re-extracted, since sanitizing drops their entries.
    """
    if content_info.get("_type", "video") != "video":
        return downloader.extract_info(url, download=True)
    info = downloader.sanitize_info(dict(content_info), remove_private_keys=True)
    try:
        return downloader.process_ie_result(info, download=True)
    except DownloadError as e:
        logger.warning(f"Download from extracted info failed, re-extracting: {e}")
        return downloader.extract_info(url, download=True)
