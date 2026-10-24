"""High-level RTP Play client: the only API the Kodi layer should use."""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Callable, List, Optional, TypeVar

from . import parsers
from .cache import Cache
from .http import DEFAULT_HEADERS, HttpClient
from .models import (
    MOVIES,
    SHOWS,
    Category,
    Channel,
    Collection,
    Episode,
    EpisodeInfo,
    Page,
    Program,
    ProgramInfo,
    Season,
    Stream,
)

T = TypeVar("T")

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

# The site's series and film collections, as linked from its home page shelves.
COLLECTIONS = (
    Collection("series-nacionais", "Séries Nacionais", SHOWS),
    Collection("series-estrangeiras", "Séries Estrangeiras", SHOWS),
    Collection("cinema-portugues", "Cinema Português", MOVIES),
    Collection("filmes", "Cinema Internacional", MOVIES),
)

# Page sizes used by the site's list endpoints. A shorter page is the last one.
PROGRAMS_PAGE_SIZE = 12
EPISODES_PAGE_SIZE = 12
SEARCH_PAGE_SIZE = 16
# A collection page lists every program at once; we split it into pages like the rest.
COLLECTION_PAGE_SIZE = 12

# How long cached pages stay fresh, in seconds. Collections and seasons change
# now and then; an episode's synopsis practically never does.
COLLECTION_TTL = 6 * 3600
PROGRAM_TTL = 24 * 3600
EPISODE_TTL = 30 * 24 * 3600
# Bump when a cached model changes shape, so old entries are ignored.
CACHE_VERSION = 1

# Headers the streaming CDN checks before serving media.
STREAM_HEADERS = {key: DEFAULT_HEADERS[key] for key in ("User-Agent", "Referer", "Origin")}


class RtpPlayClient:
    """Without a ``cache``, every call fetches from the site."""

    def __init__(self, http: Optional[HttpClient] = None, cache: Optional[Cache] = None) -> None:
        self._http = http or HttpClient()
        self._cache = cache

    def categories(self) -> List[Category]:
        return list(CATEGORIES)

    def collections(self, kind: str) -> List[Collection]:
        """The collections of one kind, SHOWS or MOVIES."""
        return [c for c in COLLECTIONS if c.kind == kind]

    def collection(self, slug: str, page: int = 1) -> Page[Program]:
        """Programs in a collection, in the site's order. Cached for COLLECTION_TTL."""
        if slug not in {c.slug for c in COLLECTIONS}:
            raise ValueError("unknown collection {!r}".format(slug))
        start = (_page(page) - 1) * COLLECTION_PAGE_SIZE
        programs = self._cached(
            "collection:" + slug,
            COLLECTION_TTL,
            lambda: parsers.parse_collection(self._http.get_text("/play/colecao/" + slug)),
            lambda data: [Program(**p) for p in data],
        )
        return Page(
            items=programs[start : start + COLLECTION_PAGE_SIZE],
            page=page,
            has_more=len(programs) > start + COLLECTION_PAGE_SIZE,
        )

    def program_info(self, program_id: int) -> ProgramInfo:
        """Synopsis, artwork, seasons and latest episode of a program. Cached for PROGRAM_TTL."""
        # The program page ignores the slug after the id, so none is needed.
        return self._cached(
            "program:{}".format(program_id),
            PROGRAM_TTL,
            lambda: parsers.parse_program_info(
                self._http.get_text("/play/p{}/".format(program_id)), program_id
            ),
            lambda data: ProgramInfo(
                **dict(data, seasons=[Season(**season) for season in data["seasons"]])
            ),
        )

    def episode_info(self, episode_path: str) -> EpisodeInfo:
        """Synopsis and duration of an episode. Cached for EPISODE_TTL."""
        _check_episode_path(episode_path)
        return self._cached(
            "episode:" + episode_path,
            EPISODE_TTL,
            lambda: parsers.parse_episode_info(self._http.get_text(episode_path)),
            lambda data: EpisodeInfo(**data),
        )

    def programs(self, category_id: int, page: int = 1) -> Page[Program]:
        """Programs in a category, alphabetically."""
        html = self._http.get_text(
            "/play/bg_l_pg/",
            {"listcategory": category_id, "listtype": "az", "type": "all", "page": _page(page)},
        )
        return _paged(parsers.parse_programs(html), page, PROGRAMS_PAGE_SIZE)

    def seasons(self, program_id: int) -> List[Season]:
        """Seasons of a program, as the site lists them; empty or one item if it has only one."""
        return self.program_info(program_id).seasons

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
        if not re.fullmatch(r"[\w-]+", channel_slug):
            raise ValueError("channel_slug must be a channel slug such as 'rtp1'")
        stream = parsers.parse_live_stream(self._http.get_text("/play/direto/" + channel_slug))
        return dataclasses.replace(stream, headers=dict(STREAM_HEADERS))

    def episode_stream(self, episode_path: str) -> Stream:
        """``episode_path`` is :attr:`Episode.path`, e.g. ``/play/p1525/e892592/a-mosca``."""
        _check_episode_path(episode_path)
        stream = parsers.parse_episode_stream(self._http.get_text(episode_path))
        return dataclasses.replace(stream, headers=dict(STREAM_HEADERS))

    def _cached(self, key: str, ttl: float, fetch: Callable[[], T], load: Callable[[Any], T]) -> T:
        if self._cache is None:
            return fetch()
        key = "v{}:{}".format(CACHE_VERSION, key)
        data = self._cache.get(key)
        if data is not None:
            return load(data)
        value = fetch()
        self._cache.set(key, _to_json(value), ttl)
        return value


def _to_json(value: Any) -> Any:
    if isinstance(value, list):
        return [dataclasses.asdict(item) for item in value]
    return dataclasses.asdict(value)


def _check_episode_path(episode_path: str) -> None:
    if not episode_path.startswith("/play/"):
        raise ValueError("episode_path must be a /play/ path")


def _page(page: int) -> int:
    if page < 1:
        raise ValueError("page must be >= 1")
    return page


def _paged(items: List[T], page: int, page_size: int) -> Page[T]:
    return Page(items=items, page=page, has_more=len(items) >= page_size)
