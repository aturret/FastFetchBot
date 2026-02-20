import asyncio

from src.config import DOWNLOAD_VIDEO_TIMEOUT
from src.services.celery_client import celery_app
from fastfetchbot_shared.utils.logger import logger


class AudioTranscribe:
    def __init__(self, audio_file: str):
        self.audio_file = audio_file

    async def transcribe(self):
        return await self._get_audio_text(self.audio_file)

    @staticmethod
    async def _get_audio_text(audio_file: str):
        logger.info(f"submitting transcribe task: {audio_file}")
        result = celery_app.send_task("file_export.transcribe", kwargs={
            "audio_file": audio_file,
        })
        response = await asyncio.to_thread(result.get, timeout=int(DOWNLOAD_VIDEO_TIMEOUT))
        return response["transcript"]
