import asyncio
import uuid
from datetime import datetime
from urllib.parse import urlparse,quote

import aiofiles.os
from pathlib import Path

import aioboto3
from botocore.exceptions import ClientError

from app.utils.logger import logger
from app.utils.network import download_file_to_local
from app.config import AWS_S3_BUCKET_NAME, AWS_REGION_NAME, AWS_DOMAIN_HOST


session = aioboto3.Session()
image_url_host = (
    AWS_DOMAIN_HOST
    if AWS_DOMAIN_HOST
    else f"{AWS_S3_BUCKET_NAME}.s3.{AWS_REGION_NAME}.amazonaws.com"
)


async def download_and_upload(url: str, referer: str = None,suite:str="test") -> str:
    urlparser = urlparse(url)
    file_name = (urlparser.netloc + urlparser.path).replace("/", "-")
    local_path = await download_file_to_local(url=url, referer=referer, file_name=file_name)
    local_path = Path(local_path)
    file_name = local_path.name
    if not local_path:
        return ""
    s3_path = await upload(
        suite=suite,
        staging_path=local_path,
        file_name=file_name,
    )
    await aiofiles.os.remove(local_path)
    return s3_path


async def upload(
    staging_path: Path,
    bucket: str = AWS_S3_BUCKET_NAME,
    suite: str = "test",
    release: str = datetime.now().strftime("%Y-%m-%d"),
    file_name: str = None,
) -> str:
    if not file_name:
        file_name = uuid.uuid4().hex
    blob_s3_key = f"{suite}/{release}/{file_name}"
    async with session.client("s3") as s3:
        try:
            with staging_path.open("rb") as spfp:
                logger.info(f"Uploading {blob_s3_key}")
                await s3.upload_fileobj(
                    spfp,
                    bucket,
                    blob_s3_key,
                )
                logger.info(f"Uploaded {file_name} to {suite}/{release}")
        except Exception as e:
            logger.error(f"Failed to upload {file_name} to {suite}/{release}, {e}")
            return ""
        image_url = f"https://{image_url_host}/{blob_s3_key}"
        urlparser = urlparse(image_url)
        quoted_url = urlparser.scheme + "://" + urlparser.netloc + quote(urlparser.path)
        return quoted_url
