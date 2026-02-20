import pytest

try:
    from pydub import AudioSegment
    from pydub.generators import Sine
    HAS_FFMPEG = True
except Exception:
    HAS_FFMPEG = False

from fastfetchbot_file_export.transcribe import milliseconds_until_sound


@pytest.mark.skipif(not HAS_FFMPEG, reason="Requires ffmpeg for audio processing")
def test_milliseconds_until_sound_no_silence():
    tone = Sine(440).to_audio_segment(duration=1000)
    result = milliseconds_until_sound(tone)
    assert result == 0


@pytest.mark.skipif(not HAS_FFMPEG, reason="Requires ffmpeg for audio processing")
def test_milliseconds_until_sound_with_silence():
    silence = AudioSegment.silent(duration=500)
    tone = Sine(440).to_audio_segment(duration=500)
    audio = silence + tone
    result = milliseconds_until_sound(audio)
    assert 450 <= result <= 510  # ~500ms of silence
