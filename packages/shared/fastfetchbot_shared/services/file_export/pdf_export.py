"""Async PDF export via Celery task submission.

This module wraps the synchronous pdf_export logic with an async interface
that submits work to a Celery worker and awaits the result. The Celery app
and timeout are injected — no app-specific config imports.
"""

import asyncio
import uuid

from bs4 import BeautifulSoup
from fastfetchbot_shared.utils.logger import logger


class PdfExport:
    """Async PDF export that submits a Celery task and awaits the result.

    Args:
        title: Document title (used for output filename).
        html_string: HTML content to convert to PDF.
        celery_app: A Celery application instance for task submission.
        timeout: Timeout in seconds for the Celery task. Default: 600.
    """

    def __init__(
        self,
        title: str,
        html_string: str,
        celery_app,
        timeout: int = 600,
    ):
        self.title = title
        self.html_string = html_string
        self.celery_app = celery_app
        self.timeout = timeout

    async def export(self) -> str:
        """Submit PDF export task to Celery and return the output filename."""
        html_string = wrap_html_string(self.html_string)
        output_filename = f"{self.title}-{uuid.uuid4()}.pdf"

        logger.info(f"Submitting pdf export task: {output_filename}")
        result = self.celery_app.send_task(
            "file_export.pdf_export",
            kwargs={
                "html_string": html_string,
                "output_filename": output_filename,
            },
        )
        try:
            response = await asyncio.to_thread(
                result.get, timeout=int(self.timeout)
            )
            output_filename = response["output_filename"]
        except Exception:
            logger.exception(
                f"file_export.pdf_export task failed: "
                f"output_filename={output_filename}, timeout={self.timeout}"
            )
            raise

        logger.info(f"PDF export success: {output_filename}")
        return output_filename


def wrap_html_string(html_string: str) -> str:
    """Wrap raw HTML content in a proper document structure and strip inline styles."""
    soup = BeautifulSoup(
        '<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        '<meta charset="UTF-8"></head><body></body></html>',
        "html.parser",
    )
    soup.body.append(BeautifulSoup(html_string, "html.parser"))
    for tag in soup.find_all(True):
        if "style" in tag.attrs:
            del tag["style"]
    for style_tag in soup.find_all("style"):
        style_tag.decompose()
    return soup.prettify()
