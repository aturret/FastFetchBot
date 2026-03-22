"""Async audio transcription via Celery task submission.

This module wraps the synchronous transcribe logic with an async interface
that submits work to a Celery worker and awaits the result. The Celery app
and timeout are injected — no app-specific config imports.
"""

import asyncio

from fastfetchbot_shared.utils.logger import logger


class AudioTranscribe:
    """Async audio transcription that submits a Celery task and awaits the result.

    Args:
        audio_file: Path to the audio file to transcribe.
        celery_app: A Celery application instance for task submission.
        timeout: Timeout in seconds for the Celery task. Default: 600.
    """

    def __init__(self, audio_file: str, celery_app, timeout: int = 600):
        self.audio_file = audio_file
        self.celery_app = celery_app
        self.timeout = timeout

    async def transcribe(self) -> str:
        """Submit transcription task to Celery and return the transcript text."""
        logger.info(f"Submitting transcribe task: {self.audio_file}")
        result = self.celery_app.send_task(
            "file_export.transcribe",
            kwargs={"audio_file": self.audio_file},
        )
        try:
            response = await asyncio.to_thread(
                result.get, timeout=int(self.timeout)
            )
            return response["transcript"]
        except Exception:
            logger.exception(
                f"file_export.transcribe task failed: "
                f"audio_file={self.audio_file}, timeout={self.timeout}"
            )
            raise
