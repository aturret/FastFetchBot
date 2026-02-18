import asyncio
import functools

# import gc
import os
import uuid
from pathlib import Path

import aiofiles
import aiofiles.os
import httpx
from bs4 import BeautifulSoup

from src.config import DOWNLOAD_DIR, FILE_EXPORTER_URL, DOWNLOAD_VIDEO_TIMEOUT, TEMP_DIR, AWS_STORAGE_ON
from src.services.amazon.s3 import upload as upload_to_s3
from fastfetchbot_shared.utils.logger import logger

current_directory = os.path.dirname(os.path.abspath(__file__))

PDF_STYLESHEET = os.path.join(current_directory, "pdf_export.css")


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

    async def export(self, method: str = "file") -> str:
        body = {
            "method": method
        }
        html_string = self.wrap_html_string(self.html_string)
        if method == "string":
            body["html_string"] = html_string,
            logger.debug(
                f"""
                    html_string: {html_string}
                    """
            )
        elif method == "file":
            filename = f"{self.title}-{uuid.uuid4()}.html"
            filename = os.path.join(TEMP_DIR, filename)
            async with aiofiles.open(
                filename, "w", encoding="utf-8"
            ) as f:
                await f.write(html_string)
                html_file = filename
                logger.debug(html_file)
            body["html_file"] = html_file
        output_filename = f"{self.title}-{uuid.uuid4()}.pdf"
        body["output_filename"] = output_filename

        async with httpx.AsyncClient() as client:
            request_url = FILE_EXPORTER_URL + "/pdfExport"
            logger.info(f"requesting pdf export from pdf server: {body}")
            resp = await client.post(
                request_url, json=body, timeout=DOWNLOAD_VIDEO_TIMEOUT
            )
        output_filename = resp.json().get("output_filename")
        logger.info(f"pdf export success: {output_filename}")
        await aiofiles.os.remove(html_file)
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
