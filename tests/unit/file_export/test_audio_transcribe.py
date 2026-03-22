"""Tests for packages/shared/fastfetchbot_shared/services/file_export/audio_transcribe.py"""

from unittest.mock import MagicMock

import pytest

from fastfetchbot_shared.services.file_export.audio_transcribe import AudioTranscribe


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestAudioTranscribeInit:
    def test_stores_all_fields(self):
        mock_celery = MagicMock()
        at = AudioTranscribe(
            audio_file="/tmp/audio.mp3",
            celery_app=mock_celery,
            timeout=300,
        )
        assert at.audio_file == "/tmp/audio.mp3"
        assert at.celery_app is mock_celery
        assert at.timeout == 300

    def test_default_timeout(self):
        mock_celery = MagicMock()
        at = AudioTranscribe(audio_file="/tmp/a.mp3", celery_app=mock_celery)
        assert at.timeout == 600


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        mock_result = MagicMock()
        mock_result.get.return_value = {"transcript": "Hello world, this is a test."}
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        at = AudioTranscribe(
            audio_file="/tmp/audio.mp3",
            celery_app=mock_celery,
            timeout=120,
        )
        text = await at.transcribe()

        assert text == "Hello world, this is a test."

    @pytest.mark.asyncio
    async def test_transcribe_sends_correct_task(self):
        mock_result = MagicMock()
        mock_result.get.return_value = {"transcript": "ok"}
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        at = AudioTranscribe(
            audio_file="/tmp/speech.wav", celery_app=mock_celery
        )
        await at.transcribe()

        mock_celery.send_task.assert_called_once_with(
            "file_export.transcribe",
            kwargs={"audio_file": "/tmp/speech.wav"},
        )

    @pytest.mark.asyncio
    async def test_transcribe_uses_timeout(self):
        mock_result = MagicMock()
        mock_result.get.return_value = {"transcript": "ok"}
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        at = AudioTranscribe(audio_file="f", celery_app=mock_celery, timeout=99)
        await at.transcribe()

        mock_result.get.assert_called_once_with(timeout=99)

    @pytest.mark.asyncio
    async def test_transcribe_failure_reraises(self):
        mock_result = MagicMock()
        mock_result.get.side_effect = RuntimeError("transcription failed")
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        at = AudioTranscribe(audio_file="f", celery_app=mock_celery)

        with pytest.raises(RuntimeError, match="transcription failed"):
            await at.transcribe()

    @pytest.mark.asyncio
    async def test_transcribe_timeout_error(self):
        mock_result = MagicMock()
        mock_result.get.side_effect = TimeoutError("celery timeout")
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        at = AudioTranscribe(audio_file="f", celery_app=mock_celery)

        with pytest.raises(TimeoutError):
            await at.transcribe()
