import os
import sys

import pytest
from requests.structures import CaseInsensitiveDict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = CaseInsensitiveDict(headers or {})
        self.closed = False

    def close(self):
        self.closed = True


class FakeSession:
    """Replays queued responses (or raises queued exceptions) and records requests."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, params=None, headers=None, timeout=None, stream=False):
        self.requests.append(
            {"url": url, "params": params, "headers": headers, "timeout": timeout, "stream": stream}
        )
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeClock:
    """Monotonic clock whose ``sleep`` just advances time."""

    def __init__(self, start=1000.0):
        self.now = start
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()
