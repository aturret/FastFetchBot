from worker_core.main import app
from worker_core.config import OPENAI_API_KEY
from fastfetchbot_file_export.transcribe import get_audio_text


@app.task(name="file_export.transcribe")
def transcribe_task(audio_file: str, openai_api_key: str = None) -> dict:
    api_key = openai_api_key or OPENAI_API_KEY
    transcript = get_audio_text(audio_file, api_key)
    return {"transcript": transcript, "message": "ok"}
