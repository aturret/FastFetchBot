# coding=utf8

from urllib.parse import urlparse, urljoin
import logging
from .upload_images import upload_image
from .converter import _fragments_from_string
import lxml.html
import concurrent.futures

from app.services.amazon.s3 import download_and_upload as upload_image_to_s3
from app.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_S3_BUCKET_NAME, AWS_STORAGE_ON,
)
from ...utils.logger import logger

LOG = logging.getLogger(__name__)


class DocumentPreprocessor:
    def __init__(self, input_document, url: str = None):
        self.url = url
        self.input_document = input_document
        self.parsed_document = self._parse_document()

    def get_processed_html(self):
        return lxml.html.tostring(self.parsed_document, encoding="unicode")

    @staticmethod
    async def _upload_image(url):
        new_image_url = None
        try:
            new_image_url = await upload_image(url)
        except Exception:
            logger.error(f"Could not upload image {url}")

        return new_image_url

    async def upload_all_images(self, base_url=None):
        self._make_links_absolute(base_url)
        images = self.parsed_document.xpath(
            './/img[@src][not(contains(@src, "//telegra.ph/file/")) and'
            ' not(contains(@src, "//graph.org/file/"))]'
        )

        for image in images:
            logger.debug(f"Uploading image {image.attrib.get('src')}")
            await DocumentPreprocessor._upload_and_replace_url(image, url=self.url)

    @staticmethod
    async def _upload_and_replace_url(image_element, url: str = None):
        old_image_url = image_element.attrib.get("src")
        if AWS_STORAGE_ON:
            new_image_url = await DocumentPreprocessor._upload_image_to_s3(
                old_image_url, url=url
            )
        else:
            new_image_url = await DocumentPreprocessor._upload_image(old_image_url)
        if new_image_url:
            image_element.attrib.update({"src": new_image_url})

    def _parse_document(self):
        if isinstance(self.input_document, str):
            fragments = _fragments_from_string(self.input_document)
            document = fragments[0].xpath("/*")[0] if len(fragments) else None
        elif isinstance(self.input_document, lxml.html.HtmlMixin):
            document = self.input_document.xpath("/*")[0]
        else:
            raise TypeError(
                "DocumentPreprocessor accepts only html string or lxml document object"
            )

        return document

    def _make_links_absolute(self, base_url=None):
        body = self.parsed_document.body
        output_base = None
        document_base_url = self.parsed_document.base

        if base_url:
            urlformat = urlparse(base_url)
            url_without_path = urlformat.scheme + "://" + urlformat.netloc
            output_base = url_without_path + urlformat.path
        elif document_base_url:
            if urlparse(document_base_url).netloc:
                output_base = document_base_url

        if output_base is None:
            # no base_url was passed, document_base_url is missing
            LOG.warning("Relative image/link urls were removed from the document")

        def link_replace(href):
            try:
                if output_base is None and not urlparse(href).netloc:
                    url = None
                else:
                    url = urljoin(output_base, href)
                return url
            except ValueError:
                return None

        body.rewrite_links(link_repl_func=link_replace, base_href=output_base)

    @staticmethod
    async def _upload_image_to_s3(old_image_url, url: str = None):
        new_image_url = None
        try:
            new_image_url = await upload_image_to_s3(old_image_url, referer=url, suite="images")
        except Exception as e:
            logger.error(f"Could not upload image {old_image_url}\nError: {e}")
        return new_image_url
