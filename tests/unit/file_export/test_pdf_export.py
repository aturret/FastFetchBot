"""Tests for packages/shared/fastfetchbot_shared/services/file_export/pdf_export.py"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from fastfetchbot_shared.services.file_export.pdf_export import PdfExport, wrap_html_string


# ---------------------------------------------------------------------------
# wrap_html_string (pure function)
# ---------------------------------------------------------------------------


class TestWrapHtmlString:
    def test_wraps_in_html_document(self):
        result = wrap_html_string("<p>Hello</p>")
        assert "<html>" in result
        assert "<head>" in result
        assert "<body>" in result
        assert "Hello" in result

    def test_includes_utf8_meta_tags(self):
        result = wrap_html_string("<p>test</p>")
        assert 'charset="UTF-8"' in result or "charset=utf-8" in result.lower()

    def test_strips_inline_styles(self):
        html = '<p style="color: red;">styled text</p>'
        result = wrap_html_string(html)
        assert 'style=' not in result
        assert "styled text" in result

    def test_removes_style_tags(self):
        html = "<style>body { color: red; }</style><p>content</p>"
        result = wrap_html_string(html)
        assert "<style>" not in result
        assert "content" in result

    def test_strips_multiple_inline_styles(self):
        html = '<div style="margin: 0;"><span style="font-size: 12px;">text</span></div>'
        result = wrap_html_string(html)
        assert 'style=' not in result
        assert "text" in result

    def test_preserves_non_style_attributes(self):
        html = '<a href="https://example.com" class="link">click</a>'
        result = wrap_html_string(html)
        assert "https://example.com" in result
        assert "click" in result

    def test_empty_html_raises(self):
        """Empty string causes BS4 IndexError — callers should validate input."""
        with pytest.raises(IndexError):
            wrap_html_string("")

    def test_special_characters(self):
        html = "<p>Emoji: \U0001f600 & special < > chars</p>"
        result = wrap_html_string(html)
        assert "\U0001f600" in result


# ---------------------------------------------------------------------------
# PdfExport.__init__
# ---------------------------------------------------------------------------


class TestPdfExportInit:
    def test_stores_all_fields(self):
        mock_celery = MagicMock()
        pdf = PdfExport(
            title="Test Doc",
            html_string="<p>hi</p>",
            celery_app=mock_celery,
            timeout=300,
        )
        assert pdf.title == "Test Doc"
        assert pdf.html_string == "<p>hi</p>"
        assert pdf.celery_app is mock_celery
        assert pdf.timeout == 300

    def test_default_timeout(self):
        mock_celery = MagicMock()
        pdf = PdfExport(title="t", html_string="h", celery_app=mock_celery)
        assert pdf.timeout == 600


# ---------------------------------------------------------------------------
# PdfExport.export
# ---------------------------------------------------------------------------


class TestPdfExportExport:
    @pytest.mark.asyncio
    async def test_export_success(self):
        mock_result = MagicMock()
        mock_result.get.return_value = {"output_filename": "/tmp/final.pdf"}
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        pdf = PdfExport(
            title="My Doc",
            html_string="<p>content</p>",
            celery_app=mock_celery,
            timeout=120,
        )
        output = await pdf.export()

        assert output == "/tmp/final.pdf"
        mock_celery.send_task.assert_called_once_with(
            "file_export.pdf_export",
            kwargs={
                "html_string": mock_celery.send_task.call_args.kwargs["kwargs"]["html_string"],
                "output_filename": mock_celery.send_task.call_args.kwargs["kwargs"]["output_filename"],
            },
        )

    @pytest.mark.asyncio
    async def test_export_sends_correct_task_name(self):
        mock_result = MagicMock()
        mock_result.get.return_value = {"output_filename": "/tmp/out.pdf"}
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        pdf = PdfExport(title="t", html_string="<p>x</p>", celery_app=mock_celery)
        await pdf.export()

        args, kwargs = mock_celery.send_task.call_args
        assert args[0] == "file_export.pdf_export"

    @pytest.mark.asyncio
    async def test_export_output_filename_contains_title(self):
        mock_result = MagicMock()
        mock_result.get.return_value = {"output_filename": "/tmp/out.pdf"}
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        pdf = PdfExport(title="MyTitle", html_string="<p>x</p>", celery_app=mock_celery)
        await pdf.export()

        sent_kwargs = mock_celery.send_task.call_args.kwargs["kwargs"]
        assert sent_kwargs["output_filename"].startswith("MyTitle-")
        assert sent_kwargs["output_filename"].endswith(".pdf")

    @pytest.mark.asyncio
    async def test_export_wraps_html_before_sending(self):
        mock_result = MagicMock()
        mock_result.get.return_value = {"output_filename": "/tmp/out.pdf"}
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        pdf = PdfExport(title="t", html_string="<p>raw</p>", celery_app=mock_celery)
        await pdf.export()

        sent_kwargs = mock_celery.send_task.call_args.kwargs["kwargs"]
        # Should be wrapped (has <html> tags from wrap_html_string)
        assert "<html>" in sent_kwargs["html_string"]
        assert "raw" in sent_kwargs["html_string"]

    @pytest.mark.asyncio
    async def test_export_uses_timeout(self):
        mock_result = MagicMock()
        mock_result.get.return_value = {"output_filename": "/tmp/out.pdf"}
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        pdf = PdfExport(title="t", html_string="h", celery_app=mock_celery, timeout=42)
        await pdf.export()

        mock_result.get.assert_called_once_with(timeout=42)

    @pytest.mark.asyncio
    async def test_export_celery_failure_reraises(self):
        mock_result = MagicMock()
        mock_result.get.side_effect = TimeoutError("task timed out")
        mock_celery = MagicMock()
        mock_celery.send_task.return_value = mock_result

        pdf = PdfExport(title="t", html_string="h", celery_app=mock_celery)

        with pytest.raises(TimeoutError, match="task timed out"):
            await pdf.export()
