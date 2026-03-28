"""Tests for exception handling in packages/file-export/fastfetchbot_file_export/pdf_export.py"""

import sys
from unittest.mock import patch, MagicMock

import pytest

from fastfetchbot_shared.exceptions import FileExportError


@pytest.fixture(autouse=True)
def mock_weasyprint(monkeypatch):
    """Mock weasyprint to avoid native library dependency."""
    mock_module = MagicMock()
    monkeypatch.setitem(sys.modules, "weasyprint", mock_module)
    monkeypatch.setitem(sys.modules, "weasyprint.text", MagicMock())
    monkeypatch.setitem(sys.modules, "weasyprint.text.fonts", MagicMock())
    # Force reimport of pdf_export with mocked weasyprint
    if "fastfetchbot_file_export.pdf_export" in sys.modules:
        del sys.modules["fastfetchbot_file_export.pdf_export"]


class TestExportPdfExceptionHandling:
    def test_raises_file_export_error_on_failure(self):
        from fastfetchbot_file_export.pdf_export import export_pdf

        with patch(
            "fastfetchbot_file_export.pdf_export.convert_html_to_pdf",
            side_effect=RuntimeError("WeasyPrint crashed"),
        ):
            with pytest.raises(FileExportError, match="PDF export failed"):
                export_pdf(html_string="<p>test</p>", output_filename="test.pdf")

    def test_preserves_original_cause(self):
        from fastfetchbot_file_export.pdf_export import export_pdf

        original = OSError("disk full")
        with patch(
            "fastfetchbot_file_export.pdf_export.convert_html_to_pdf",
            side_effect=original,
        ):
            with pytest.raises(FileExportError) as exc_info:
                export_pdf(html_string="<p>x</p>", output_filename="out.pdf")
            assert exc_info.value.__cause__ is original


class TestConvertHtmlToPdf:
    def test_no_input_raises_file_export_error(self):
        from fastfetchbot_file_export.pdf_export import convert_html_to_pdf

        with pytest.raises(FileExportError, match="Either html_string or html_file"):
            convert_html_to_pdf("output.pdf")
