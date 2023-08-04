from io import BytesIO


class NamedBytesIO(BytesIO):
    @property
    def name(self):
        return self._name

    def __init__(self, content=None, name=None):
        super().__init__(content)
        self._name = name
        if content is not None:
            self.size = self.getbuffer().nbytes

    @name.setter
    def name(self, value):
        self._name = value
