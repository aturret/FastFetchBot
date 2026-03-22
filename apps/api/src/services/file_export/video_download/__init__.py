"""API-layer video downloader — wraps the shared VideoDownloader with API config."""

from typing import Any, Optional

from fastfetchbot_shared.services.file_export.video_download import VideoDownloader as BaseVideoDownloader
from src.services.celery_client import celery_app
from src.config import DOWNLOAD_VIDEO_TIMEOUT


class VideoDownloader(BaseVideoDownloader):
    """API VideoDownloader that injects the API's Celery app and timeout."""

    def __init__(
        self,
        url: str,
        category: str,
        data: Optional[Any] = None,
        download: bool = True,
        audio_only: bool = False,
        hd: bool = False,
        transcribe: bool = False,
        **kwargs,
    ):
        super().__init__(
            url=url,
            category=category,
            celery_app=celery_app,
            timeout=DOWNLOAD_VIDEO_TIMEOUT,
            data=data,
            download=download,
            audio_only=audio_only,
            hd=hd,
            transcribe=transcribe,
            **kwargs,
        )
