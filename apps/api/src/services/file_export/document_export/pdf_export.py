"""API-layer PDF export — extends the shared PdfExport with S3 upload support."""

from pathlib import Path

import aiofiles.os

from fastfetchbot_shared.services.file_export.pdf_export import PdfExport as BasePdfExport, wrap_html_string
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


class PdfExport(BasePdfExport):
    """API PDF export that adds optional S3 upload after Celery PDF generation."""

    def __init__(self, title: str, html_string: str = None):
        super().__init__(
            title=title,
            html_string=html_string,
            celery_app=celery_app,
            timeout=DOWNLOAD_VIDEO_TIMEOUT,
        )

    async def export(self) -> str:
        output_filename = await super().export()

        if AWS_STORAGE_ON:
            local_filename = output_filename
            output_filename = await upload_file_to_s3(Path(output_filename))
            await aiofiles.os.remove(local_filename)

        return output_filename
