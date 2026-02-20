import os

from pydub import AudioSegment
from openai import OpenAI
from loguru import logger

TRANSCRIBE_MODEL = "whisper-1"
SEGMENT_LENGTH = 5 * 60  # 5 minutes in seconds

PUNCTUATION_SYSTEM_PROMPT = (
    "You are a helpful assistant. Your job is to adds punctuation to text. "
    "What you are going to do should follow the rules below: \n"
    '1. You have received a text which is transcribed from an audio file which we call it "original text".\n'
    "2. The response should be presented in the language of the original text.\n"
    "3. I need you to convert the original text into a new context. During "
    "this process, please preserve the original words of the given original text and only insert "
    "necessary punctuation such as periods, commas, capitalization, symbols like dollar signs or "
    "percentage signs, and formatting according to the language of the provided original text. And I "
    "hope you to separate the original text into several paragraphs based on the meaning. Please "
    "use only the provided original text. \n"
)

SUMMARY_SYSTEM_PROMPT = (
    "You are a helpful assistant. Your job is to summarize text. "
    "What you are going to do should follow the rules below: \n"
    '1. You have received a text which we call it "original text".\n'
    "2. The response should be presented in the language of the original text.\n"
    "3. I need you to make a brief statement of the main points of the original text."
    "Please use only the provided original text. \n"
)


def milliseconds_until_sound(sound, silence_threshold_in_decibels=-20.0, chunk_size=10):
    """Find the number of milliseconds until the first non-silent part."""
    trim_ms = 0
    assert chunk_size > 0
    while (
        sound[trim_ms : trim_ms + chunk_size].dBFS < silence_threshold_in_decibels
        and trim_ms < len(sound)
    ):
        trim_ms += chunk_size
    return trim_ms


def punctuation_assistant(client: OpenAI, transcript: str) -> str:
    """Use GPT to add punctuation and formatting to raw transcript."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-16k",
        temperature=0,
        messages=[
            {"role": "system", "content": PUNCTUATION_SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    return response.choices[0].message.content


def summary_assistant(client: OpenAI, transcript: str) -> str:
    """Use GPT to generate a summary of the transcript."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-16k",
        temperature=0,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    return response.choices[0].message.content


def get_audio_text(audio_file: str, openai_api_key: str) -> str:
    """
    Transcribe an audio file using OpenAI Whisper, then post-process with GPT.

    Returns formatted string with summary and full transcript.
    """
    client = OpenAI(api_key=openai_api_key)
    transcript = ""
    AudioSegment.converter = "ffmpeg"
    audio_file_non_ext, audio_file_ext = os.path.splitext(audio_file)
    ext = audio_file_ext.lstrip(".")
    audio_item = AudioSegment.from_file(audio_file, ext)
    start_trim = milliseconds_until_sound(audio_item)
    audio_item = audio_item[start_trim:]
    audio_length = int(audio_item.duration_seconds) + 1

    for index, i in enumerate(range(0, audio_length * 1000, SEGMENT_LENGTH * 1000)):
        start_time = i
        end_time = i + SEGMENT_LENGTH * 1000
        if end_time >= audio_length * 1000:
            audio_segment = audio_item[start_time:]
        else:
            audio_segment = audio_item[start_time:end_time]

        segment_path = f"{audio_file_non_ext}-{index + 1}{audio_file_ext}"
        audio_segment.export(segment_path)
        logger.info(f"audio_segment_path: {segment_path}")

        with open(segment_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model=TRANSCRIBE_MODEL, file=f
            )
            transcript += result.text

        os.remove(segment_path)

    transcript = punctuation_assistant(client, transcript)
    transcript = (
        f"全文总结：\n{summary_assistant(client, transcript)}\n原文：\n{transcript}"
    )
    logger.info(f"transcript: {transcript}")
    os.remove(audio_file)
    return transcript
