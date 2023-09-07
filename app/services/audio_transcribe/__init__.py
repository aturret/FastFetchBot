import httpx

from app.config import OPENAI_API_KEY, FILE_EXPORTER_URL, DOWNLOAD_VIDEO_TIMEOUT
from app.utils.logger import logger
from app.utils.parse import wrap_text_into_html

TRANSCRIBE_MODEL = "whisper-1"
SEGMENT_LENGTH = 5 * 60


class AudioTranscribe:
    def __init__(self, audio_file: str):
        self.audio_file = audio_file

    async def transcribe(self):
        return await self._get_audio_text(self.audio_file)

    @staticmethod
    async def _get_audio_text(audio_file: str):
        async with httpx.AsyncClient() as client:
            body = {
                "audio_file": audio_file,
                "openai_api_key": OPENAI_API_KEY,
            }
            request_url = FILE_EXPORTER_URL + "/transcribe"
            response = await client.post(
                url=request_url, json=body, timeout=DOWNLOAD_VIDEO_TIMEOUT
            )
            transcript = response.json().get("transcript")
            transcript = wrap_text_into_html(transcript)
            return transcript
