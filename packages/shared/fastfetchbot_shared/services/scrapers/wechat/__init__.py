from typing import Dict, Any, Optional

from lxml import etree
from bs4 import BeautifulSoup, NavigableString

from fastfetchbot_shared.models.metadata_item import MetadataItem, MediaFile, MessageType
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.network import get_selector, HEADERS


class Wechat(MetadataItem):
    def __init__(self, url: str, data: Optional[Any] = None, **kwargs):
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
        return meta_data

    def _process_wechat(self, wechat_data: Dict) -> None:
        self.title = wechat_data["title"]
        self.author = wechat_data["author"]
        self.author_url = ""
        soup = BeautifulSoup(wechat_data["content"], "lxml")
        for img_item in soup.find_all("img"):
            if img_item.get("class") and all(
                    elem in img_item.get("class") for elem in ["rich_pages", "wxw-img"]
            ):
                img_url = img_item["data-src"]
                img_item["src"] = img_url
                img_item["data-src"] = img_url
                self.media_files.append(MediaFile(url=img_url, media_type="image"))
        for section_tag in soup.find_all("section"):
            # if no p tag in section tag, then we consider that all text tags are span tags. We divide paragraphs by
            # <br/><br/> tags pair, unwrap all other tags, and wrap them with <p> tags.
            if not section_tag.find_all("section"):
                new_p_tag = soup.new_tag("p")
                contents = section_tag.contents[:]
                for content in contents:
                    content.extract()
                for content in contents:
                    if (
                            content.name == "br"
                            and content.next_sibling
                            and content.next_sibling.name == "br"
                    ):
                        content.decompose()
                        content.next_sibling.decompose()
                        if new_p_tag.contents:
                            section_tag.append(new_p_tag)
                            new_p_tag = soup.new_tag("p")
                    elif content.name == "p":
                        if new_p_tag.contents:
                            section_tag.append(new_p_tag)
                            new_p_tag = soup.new_tag("p")
                        section_tag.append(content)
                    else:
                        new_p_tag.append(content)
                if new_p_tag.contents:
                    section_tag.append(new_p_tag)
        self.raw_content = str(soup)
        self.content = self.raw_content
        self.text = soup.get_text()
