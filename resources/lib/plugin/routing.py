"""Plugin URLs: ``plugin://plugin.video.modernrtpplay/?action=<name>&<params>``."""

from __future__ import annotations

from typing import Dict, List, NamedTuple
from urllib.parse import parse_qsl, urlencode


class Request(NamedTuple):
    base_url: str
    handle: int
    params: Dict[str, str]


def parse_argv(argv: List[str]) -> Request:
    """Kodi calls plugins with ``[base_url, handle, '?query']``."""
    query = argv[2][1:] if len(argv) > 2 and argv[2].startswith("?") else ""
    return Request(base_url=argv[0], handle=int(argv[1]), params=dict(parse_qsl(query)))


def build_url(base_url: str, action: str, **params: object) -> str:
    query = {"action": action}
    query.update({key: str(value) for key, value in params.items() if value is not None})
    return "{}?{}".format(base_url, urlencode(query))
