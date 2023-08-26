# TODO: https://rapidapi.com/arraybobo/api/instagram-scraper-2022

from app.models.metadata_item import MetadataItem


class Instagram(MetadataItem):
    def __init__(self):
        pass

    async def get_item(self):
        await self.get_instagram()
        return self.to_dict()

    async def get_instagram(self):
        pass
