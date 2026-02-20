import asyncio
import uuid
from pathlib import Path

import aiofiles.os
from bs4 import BeautifulSoup

from src.config import DOWNLOAD_VIDEO_TIMEOUT, AWS_STORAGE_ON
from src.services.celery_client import celery_app
from src.services.amazon.s3 import upload as upload_to_s3
from fastfetchbot_shared.utils.logger import logger


async def upload_file_to_s3(output_filename):
    return await upload_to_s3(
        staging_path=output_filename,
        suite="documents",
        file_name=output_filename.name,
    )


class PdfExport:
    def __init__(self, title: str, html_string: str = None):
        self.title = title
        self.html_string = html_string

    async def export(self) -> str:
        html_string = self.wrap_html_string(self.html_string)
        output_filename = f"{self.title}-{uuid.uuid4()}.pdf"

        logger.info(f"submitting pdf export task: {output_filename}")
        result = celery_app.send_task("file_export.pdf_export", kwargs={
            "html_string": html_string,
            "output_filename": output_filename,
        })
        try:
            response = await asyncio.to_thread(result.get, timeout=int(DOWNLOAD_VIDEO_TIMEOUT))
            output_filename = response["output_filename"]
        except Exception:
            logger.exception(
                f"file_export.pdf_export task failed: output_filename={output_filename}, "
                f"timeout={DOWNLOAD_VIDEO_TIMEOUT}"
            )
            raise
        logger.info(f"pdf export success: {output_filename}")

        if AWS_STORAGE_ON:
            local_filename = output_filename
            output_filename = await upload_file_to_s3(Path(output_filename))
            await aiofiles.os.remove(local_filename)
        return output_filename

    @staticmethod
    def wrap_html_string(html_string: str) -> str:
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
