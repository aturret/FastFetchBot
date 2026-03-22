"""API-layer audio transcription — wraps the shared AudioTranscribe with API config."""

from fastfetchbot_shared.services.file_export.audio_transcribe import AudioTranscribe as BaseAudioTranscribe
from src.services.celery_client import celery_app
from src.config import DOWNLOAD_VIDEO_TIMEOUT


class AudioTranscribe(BaseAudioTranscribe):
    """API AudioTranscribe that injects the API's Celery app and timeout."""

    def __init__(self, audio_file: str):
        super().__init__(
            audio_file=audio_file,
            celery_app=celery_app,
            timeout=DOWNLOAD_VIDEO_TIMEOUT,
        )
