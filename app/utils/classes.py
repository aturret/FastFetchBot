import io


class NamedBytesIO(io.BytesIO):
    def __init__(self, content, name):
        super().__init__(content)
        self.name = name
        self.size = self.getbuffer().nbytes
