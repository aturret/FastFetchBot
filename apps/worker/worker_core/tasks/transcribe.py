from worker_core.main import app
from worker_core.config import OPENAI_API_KEY
from fastfetchbot_file_export.transcribe import get_audio_text
from fastfetchbot_shared.utils.logger import logger


@app.task(name="file_export.transcribe")
def transcribe_task(audio_file: str) -> dict:
    logger.info(f"transcribe_task started: audio_file={audio_file}")
    if not OPENAI_API_KEY:
        logger.error("transcribe_task failed: OPENAI_API_KEY is not set")
        raise ValueError("OPENAI_API_KEY is not configured in the worker environment")
    try:
        transcript = get_audio_text(audio_file, OPENAI_API_KEY)
    except Exception:
        logger.exception(f"transcribe_task failed: audio_file={audio_file}")
        raise
    logger.info(f"transcribe_task completed: audio_file={audio_file}, transcript length={len(transcript)}")
    return {"transcript": transcript, "message": "ok"}
