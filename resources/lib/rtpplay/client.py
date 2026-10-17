"""High-level RTP Play client: the only API the Kodi layer should use."""

from __future__ import annotations

import dataclasses
from typing import List, Optional

from . import parsers
from .http import DEFAULT_HEADERS, HttpClient
from .models import Category, Channel, Episode, Page, Program, Stream

# Category ids are what the site's list endpoints filter on. They are not
# exposed anywhere cheap to scrape (each needs its own page fetch), and they
# have not changed since the old mobile API, so they are kept here.
CATEGORIES = (
    Category(1, "informacao", "Informação"),
    Category(2, "cultura", "Cultura"),
    Category(3, "humor", "Humor"),
    Category(4, "musica", "Música"),
    Category(5, "desporto", "Desporto"),
    Category(6, "infantis-e-juvenis", "Infantis e Juvenis"),
    Category(7, "institucionais", "Institucionais"),
    Category(8, "outros", "Outros"),
    Category(9, "ficcao", "Ficção"),
    Category(10, "entretenimento", "Entretenimento"),
    Category(11, "ciencia-e-natureza", "Ciência e Natureza"),
    Category(12, "entrevista-opiniao-e-debate", "Entrevista, Opinião e Debate"),
    Category(13, "gastronomia", "Gastronomia"),
    Category(14, "artes", "Artes"),
    Category(15, "religiosos-e-reflexao", "Religiosos e Reflexão"),
    Category(16, "saude", "Saúde"),
    Category(17, "especiais", "Especiais"),
)

# Page sizes used by the site's list endpoints. A shorter page is the last one.
PROGRAMS_PAGE_SIZE = 12
EPISODES_PAGE_SIZE = 12
SEARCH_PAGE_SIZE = 16

# Headers the streaming CDN checks before serving media.
STREAM_HEADERS = {key: DEFAULT_HEADERS[key] for key in ("User-Agent", "Referer", "Origin")}


class RtpPlayClient:
    def __init__(self, http: Optional[HttpClient] = None) -> None:
        self._http = http or HttpClient()

    def categories(self) -> List[Category]:
        return list(CATEGORIES)

    def programs(self, category_id: int, page: int = 1) -> Page[Program]:
        """Programs in a category, alphabetically."""
        html = self._http.get_text(
            "/play/bg_l_pg/",
            {"listcategory": category_id, "listtype": "az", "type": "all", "page": _page(page)},
        )
        return _paged(parsers.parse_programs(html), page, PROGRAMS_PAGE_SIZE)

    def episodes(self, program_id: int, page: int = 1) -> Page[Episode]:
        """Episodes of a program, newest first."""
        html = self._http.get_text(
            "/play/bg_l_ep/", {"listProgram": program_id, "type": "all", "page": _page(page)}
        )
        return _paged(parsers.parse_episodes(html), page, EPISODES_PAGE_SIZE)

    def search(self, query: str, page: int = 1) -> Page[Episode]:
        if not query.strip():
            raise ValueError("query must not be empty")
        html = self._http.get_text(
            "/play/bg_l_s/", {"listQuery": query.strip(), "type": "all", "page": _page(page)}
        )
        return _paged(parsers.parse_episodes(html), page, SEARCH_PAGE_SIZE)

    def live_channels(self) -> List[Channel]:
        return parsers.parse_live_channels(self._http.get_text("/play/direto"))

    def live_stream(self, channel_slug: str) -> Stream:
        stream = parsers.parse_live_stream(self._http.get_text("/play/direto/" + channel_slug))
        return dataclasses.replace(stream, headers=dict(STREAM_HEADERS))

    def episode_stream(self, episode_path: str) -> Stream:
        """``episode_path`` is :attr:`Episode.path`, e.g. ``/play/p1525/e892592/a-mosca``."""
        if not episode_path.startswith("/play/"):
            raise ValueError("episode_path must be a /play/ path")
        stream = parsers.parse_episode_stream(self._http.get_text(episode_path))
        return dataclasses.replace(stream, headers=dict(STREAM_HEADERS))


def _page(page: int) -> int:
    if page < 1:
        raise ValueError("page must be >= 1")
    return page


def _paged(items: list, page: int, page_size: int) -> Page:
    return Page(items=items, page=page, has_more=len(items) >= page_size)
