import openai

TRANSCRIBE_MODEL = "whisper"


def get_audio_text(audio_file: str):
    audio_file = open(audio_file, "rb")
    transcript = openai.Audio.transcribe(file=audio_file, model=TRANSCRIBE_MODEL)
    print(transcript.text)
