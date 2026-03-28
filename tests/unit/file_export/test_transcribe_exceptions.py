"""Tests for exception handling in packages/file-export/fastfetchbot_file_export/transcribe.py"""

from unittest.mock import patch, MagicMock

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
