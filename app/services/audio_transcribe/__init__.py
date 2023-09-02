import os
import asyncio

from pydub import AudioSegment
import openai

from app.config import OPENAI_API_KEY
from app.utils.logger import logger

TRANSCRIBE_MODEL = "whisper-1"
SEGMENT_LENGTH = 5 * 60
openai.api_key = OPENAI_API_KEY


class AudioTranscribe:
    def __init__(self, audio_file: str):
        self.audio_file = audio_file

    async def transcribe(self):
        return await self._get_audio_text(self.audio_file)

    @staticmethod
    async def _get_audio_text(audio_file: str):
        loop = asyncio.get_event_loop()
        transcript = ""
        AudioSegment.converter = "ffmpeg"
        audio_item = await loop.run_in_executor(None, AudioSegment.from_file, audio_file, "m4a")
        audio_length = int(audio_item.duration_seconds) + 1
        for index, i in enumerate(range(0, SEGMENT_LENGTH * 1000, audio_length * 1000)):
            start_time = i
            end_time = (i + SEGMENT_LENGTH) * 1000
            if end_time < audio_length * 1000:
                audio_segment = audio_item[start_time:]
            else:
                audio_segment = audio_item[start_time:end_time]
            audio_file_list = audio_file.split(".")
            audio_file_ext = audio_file_list[-1]
            audio_file_non_ext = ".".join(audio_file_list[:-1])
            audio_segment_path = audio_file_non_ext + "-" + str(index + 1) + "." + audio_file_ext
            await loop.run_in_executor(None, audio_segment.export, audio_segment_path)
            logger.debug(f"audio_segment_path: {audio_segment_path}")
            audio_segment_file = await loop.run_in_executor(None, open, audio_segment_path, "rb")
            transcript_segment = await loop.run_in_executor(None, openai.Audio.transcribe,
                                                            TRANSCRIBE_MODEL,
                                                            audio_segment_file
                                                            )
            transcript += str(transcript_segment["text"]).encode("utf-8").decode("utf-8")
            await loop.run_in_executor(None, audio_segment_file.close)
            await loop.run_in_executor(None, os.remove, audio_segment_path)
        await loop.run_in_executor(None, os.remove, audio_file)
        return transcript
