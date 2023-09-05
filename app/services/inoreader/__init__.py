from bs4 import BeautifulSoup

from app.models.metadata_item import MetadataItem, MediaFile


class Inoreader(MetadataItem):

    def __init__(self, url: str, data: dict):
        self.url = url
        self.title = data.get('title')
        self.message = data.get('message')
        self.author = data.get('author')
        self.author_url = data.get('author_url')
        self.category = data.get('tag')
        self.raw_content = data.get('content')
        self.content = self.raw_content
        self.media_files = []

    async def get_item(self) -> dict:
        self._resolve_media_files()
        return self.to_dict()

    def _resolve_media_files(self):
        soup = BeautifulSoup(self.raw_content, 'html.parser')
        for img in soup.find_all('img'):
            self.media_files.append(MediaFile(url=img['src'], media_type='image'))
            img.extract()
        for video in soup.find_all('video'):
            self.media_files.append(MediaFile(url=video['src'], media_type='video'))
            video.extract()
        for tags in soup.find_all('p','span'):
            tags.unwrap()
        self.text = str(soup)
        self.text = '<a href="' + self.url + '">' + self.author + '</a>: ' + self.text

