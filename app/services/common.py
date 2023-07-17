from app.services import threads, twitter, instagram, weibo, telegraph


class InfoExtractService(object):
    def __init__(self, url_metadata, data=None, **kwargs):
        self.url = url_metadata["url"]
        self.type = url_metadata["type"]
        self.category = url_metadata["category"]
        self.data = data
        self.service_functions = {
            "instagram": self.get_instagram,
            "twitter": self.get_twitter,
            "threads": self.get_threads,
            "weibo": self.get_weibo,
            "youtube": self.get_video,
            "bilibili": self.get_video,
        }
        self.kwargs = kwargs

    async def get_item(self):
        metadata_item = await self.service_functions[self.type]()
        # TODO: check if metadata_item needs to create a telegraph page
        return

    async def get_threads(self):
        threads_item = threads.Threads(self.url, **self.kwargs)
        metadata_item = await threads_item.get_threads()
        return metadata_item

    async def get_twitter(self):
        pass

    async def get_instagram(self):
        pass

    async def get_weibo(self):
        pass

    async def get_video(self):
        pass
