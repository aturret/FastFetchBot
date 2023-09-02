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
        start_trim = await loop.run_in_executor(None, AudioTranscribe.milliseconds_until_sound, audio_item)
        audio_item = audio_item[start_trim:]
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
        post_process_response = await loop.run_in_executor(None, AudioTranscribe.punctuation_assistant, transcript)
        transcript = post_process_response['choices'][0]['message']['content']
        logger.debug(f"transcript: {transcript}")
        return transcript

    @staticmethod
    def milliseconds_until_sound(sound, silence_threshold_in_decibels=-20.0, chunk_size=10):
        trim_ms = 0  # ms
        assert chunk_size > 0  # to avoid infinite loop
        while sound[trim_ms:trim_ms + chunk_size].dBFS < silence_threshold_in_decibels and trim_ms < len(sound):
            trim_ms += chunk_size
        return trim_ms

    @staticmethod
    def punctuation_assistant(ascii_transcript):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that adds punctuation to text. Preserve the original words "
                               "and only insert necessary punctuation such as periods, commas, capialization, symbols "
                               "like dollar signs or percentage signs, and formatting according to the language of the "
                               "provided context. And I hope you to separate the context into several paragraphs "
                               "based on the meaning. Use only the context provided. If there is no context provided say,"
                               " 'No context provided'\n"
                },
                {
                    "role": "user",
                    "content": ascii_transcript
                }
            ]
        )
        return response
