class FakeRequest:
    def __init__(self, method, host, path, text, start):
        self.method = method
        self.pretty_host = host
        self.path = path
        self.headers = {}
        self.raw_content = text.encode("utf-8")
        self.timestamp_start = start
        self.timestamp_end = start + 0.05
        self._text = text

    def get_text(self, strict=True):
        return self._text


class FakeResponse:
    def __init__(self, status, headers, start):
        self.status_code = status
        self.headers = dict(headers)
        self.timestamp_start = start
        self.stream = None


class FakeFlow:
    def __init__(self, request):
        self.request = request
        self.response = None
        self.metadata = {}
        self.error = None
