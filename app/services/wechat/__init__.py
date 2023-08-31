from typing import Dict

from lxml import etree
from bs4 import BeautifulSoup

from app.models.metadata_item import MetadataItem, MediaFile, MessageType
from app.utils.config import HEADERS
from app.utils.logger import logger
from app.utils.network import get_selector


class Wechat(MetadataItem):
    def __init__(self, url):
        self.url = url
        self.title = ""
        self.author = ""
        self.author_url = self.url
        self.text = ""
        self.content = ""
        self.media_files: list[MediaFile] = []
        self.category = "wechat"
        self.message_type = MessageType.LONG
        # auxiliary fields
        self.sid = ""
        self.official_account = ""
        self.date = ""

    async def get_item(self) -> dict:
        await self.get_wechat()
        return self.to_dict()

    async def get_wechat(self) -> None:
        wechat_data = await self._get_response_wechat_data()
        self._process_wechat(wechat_data)
        pass

    async def _get_response_wechat_data(self) -> Dict:
        wechat_data = await get_selector(self.url, headers=HEADERS)
        wechat_data = self._wechat_data_parse(wechat_data)
        return wechat_data

    @staticmethod
    def _wechat_data_parse(wechat_data: etree.HTML) -> Dict:
        article = wechat_data.xpath('//div[@id="js_article"]')[0]
        meta_data = {
            "title": article.xpath('string(//h1[@id="activity-name"])'),
            "author": article.xpath('string(//a[@id="js_name"])'),
            "content": str(
                etree.tostring(
                    article.xpath('//div[@id="js_content"]')[0], encoding="utf-8"
                ),
                encoding="utf-8",
            ),
        }
        for k, v in meta_data.items():
            new_string = v.replace("\n", "")
            meta_data[k] = new_string.strip()
        logger.debug(meta_data)
        return meta_data

    def _process_wechat(self, wechat_data: Dict) -> None:
        self.title = wechat_data["title"]
        self.author = wechat_data["author"]
        self.author_url = ""
        soup = BeautifulSoup(wechat_data["content"], "lxml")
        for img_item in soup.find_all("img"):
            if img_item.get("class") == ["rich_pages", "wxw-img"]:
                img_url = img_item["data-src"]
                img_item["src"] = img_url
                img_item["data-src"] = img_url
                self.media_files.append(MediaFile(url=img_url, media_type="image"))
        for a_item in soup.find_all("a"):
            parent_tag = a_item.find_parent()
            next_sibling = next(a_item.next_siblings, None)
            previous_sibling = next(a_item.previous_siblings, None)
            if next_sibling and previous_sibling and next_sibling.name == "span" and previous_sibling.name == "span":
                a_item.unwrap()
            parent_tag.string = parent_tag.text.strip()
        for span_item in soup.find_all("span"):
            if span_item.find_parent("section"):
                parent_tag = span_item.find_parent("section")
                if len(parent_tag.find_all(recursive=False)) == 1:
                    span_item.wrap(soup.new_tag("p"))
                    logger.debug("executed wrap")
                    for sub_span_item in span_item.find_all("span"):
                        sub_span_item.unwrap()
                        logger.debug("executed unwrap sub span")
                    span_item.string = span_item.text.strip()
                    text_blocks, current_text, br_count = [], "", 0
                    for content in span_item.contents:
                        if content.name == 'br':
                            br_count += 1
                            if br_count == 2:  # Two <br> tags encountered
                                text_blocks.append(current_text.strip())
                                current_text = ""
                                br_count = 0  # Reset the <br> counter
                            continue  # Skip adding <br> tags to the text
                        else:
                            current_text += str(content)
                        current_text += str(content)
                    if len(text_blocks) > 0:
                        if current_text.strip():
                            text_blocks.append(current_text.strip())
                        new_tags = []
                        for text in text_blocks:
                            p_tag = soup.new_tag("p")
                            p_tag.string = text
                            new_tags.append(p_tag)
                        span_item.replace_with(*new_tags)
        self.raw_content = soup.prettify()
        self.content = self.raw_content
        self.text = soup.get_text()
