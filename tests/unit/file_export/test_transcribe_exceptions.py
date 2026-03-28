"""Tests for exception handling in packages/file-export/fastfetchbot_file_export/transcribe.py"""

from unittest.mock import patch, MagicMock, mock_open

import pytest

from fastfetchbot_shared.exceptions import FileExportError


class TestGetAudioTextExceptionHandling:
    def test_raises_file_export_error_on_failure(self):
        from fastfetchbot_file_export.transcribe import get_audio_text

        with patch(
            "fastfetchbot_file_export.transcribe.OpenAI",
            side_effect=RuntimeError("API key invalid"),
        ):
            with pytest.raises(FileExportError, match="Audio transcription failed"):
                get_audio_text("/tmp/nonexistent.mp3", "fake-key")

    def test_preserves_original_cause(self):
        from fastfetchbot_file_export.transcribe import get_audio_text

        original = RuntimeError("connection refused")
        with patch(
            "fastfetchbot_file_export.transcribe.OpenAI",
            side_effect=original,
        ):
            with pytest.raises(FileExportError) as exc_info:
                get_audio_text("/tmp/test.mp3", "key")
            assert exc_info.value.__cause__ is original


class TestGetAudioTextHappyPath:
    def test_successful_transcription(self):
        from fastfetchbot_file_export.transcribe import get_audio_text

        # Mock OpenAI client
        mock_client = MagicMock()
        mock_transcription = MagicMock()
        mock_transcription.text = "hello world"
        mock_client.audio.transcriptions.create.return_value = mock_transcription

        mock_punctuation_response = MagicMock()
        mock_punctuation_response.choices = [MagicMock()]
        mock_punctuation_response.choices[0].message.content = "Hello, world."

        mock_summary_response = MagicMock()
        mock_summary_response.choices = [MagicMock()]
        mock_summary_response.choices[0].message.content = "A greeting."

        # Track which call we're on
        call_count = [0]
        def chat_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_punctuation_response
            return mock_summary_response

        mock_client.chat.completions.create.side_effect = chat_side_effect

        # Mock AudioSegment
        mock_audio = MagicMock()
        mock_audio.__getitem__ = MagicMock(return_value=mock_audio)
        mock_audio.duration_seconds = 10  # short audio, single segment
        mock_audio.dBFS = -10  # above silence threshold
        mock_audio.export = MagicMock()

        mock_segment = MagicMock()
        mock_segment.dBFS = -10
        mock_audio.__getitem__.return_value = mock_segment
        mock_segment.export = MagicMock()

        with patch("fastfetchbot_file_export.transcribe.OpenAI", return_value=mock_client), \
             patch("fastfetchbot_file_export.transcribe.AudioSegment") as MockAudioSegment, \
             patch("fastfetchbot_file_export.transcribe.os.remove") as mock_remove, \
             patch("fastfetchbot_file_export.transcribe.os.path.splitext", return_value=("/tmp/audio", ".mp3")), \
             patch("builtins.open", mock_open(read_data=b"audio data")), \
             patch("fastfetchbot_file_export.transcribe.milliseconds_until_sound", return_value=0):

            MockAudioSegment.from_file.return_value = mock_audio

            result = get_audio_text("/tmp/audio.mp3", "test-api-key")

        assert "Hello, world." in result
        assert "A greeting." in result
        # Should have cleaned up the original file
        mock_remove.assert_called()

    def test_audio_segment_failure_wraps_in_file_export_error(self):
        from fastfetchbot_file_export.transcribe import get_audio_text

        mock_client = MagicMock()

        with patch("fastfetchbot_file_export.transcribe.OpenAI", return_value=mock_client), \
             patch("fastfetchbot_file_export.transcribe.AudioSegment") as MockAudioSegment:

            MockAudioSegment.from_file.side_effect = FileNotFoundError("no such file")

            with pytest.raises(FileExportError, match="Audio transcription failed"):
                get_audio_text("/tmp/missing.mp3", "key")
