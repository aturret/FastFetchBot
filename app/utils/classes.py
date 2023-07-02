
class DictItem(object):
    """
    Most of the time, we need to convert a dict to an object.
    Each service would be a dictable object. This can make the information more readable.
    """
    def __init__(self, dict_data: dict, **kwargs):
        self.__dict__.update(dict_data)
        self.__dict__.update(kwargs)

    def to_dict(self):
        return self.__dict__


class TelegraphItem(DictItem):
    """
    TelegraphItem is a class based on DictItem, which specifies the attributes of a Telegraph page.
    If the program doesn't find the attribute in the dict_data, it will use the default value in case of KeyError.
    """
    def __init__(self, dict_data: dict, **kwargs):
        super().__init__(dict_data, **kwargs)
        self.title = self.__dict__.get('title', 'undefined_title')
        self.author = self.__dict__.get('author', 'undefined_author')
        self.author_url = self.__dict__.get('author_url', 'undefined_author_url')
        self.content = self.__dict__.get('content', 'undefined_content')


class MetadataItem(DictItem):
    """
    MetadataItem is a class based on DictItem, which specifies the attributes of a Metadata.
    The metadata is used to send to the telegram bot. Users can use the metadata to define their own message template.
    If the program doesn't find the attribute in the dict_data, it will use the default value in case of KeyError.
    """
    def __init__(self, dict_data: dict, **kwargs):
        super().__init__(dict_data, **kwargs)
        self.url = self.__dict__.get('url', 'undefined_url')
        self.title = self.__dict__.get('title', 'undefined_title')
        self.text = self.__dict__.get('text', 'undefined_text')
        self.author = self.__dict__.get('author', 'undefined_author')
        self.author_url = self.__dict__.get('author_url', 'undefined_author_url')
        self.content = self.__dict__.get('content', 'undefined_content')
        self.type = self.__dict__.get('type', 'undefined_type')
        self.telegraph_url = self.__dict__.get('telegraph_url', 'undefined_telegraph_url')
        self.media_files = self.__dict__.get('media_files', [])

