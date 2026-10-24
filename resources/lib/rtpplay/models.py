"""Immutable data types returned by :class:`rtpplay.client.RtpPlayClient`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")

TV = "tv"
RADIO = "radio"

SHOWS = "shows"
MOVIES = "movies"

HLS = "hls"
DASH = "dash"
PROGRESSIVE = "progressive"


@dataclass(frozen=True)
class Category:
    id: int
    slug: str
    name: str


@dataclass(frozen=True)
class Collection:
    """A curated list of programs, e.g. foreign series or Portuguese films."""

    slug: str  # e.g. "filmes", the page /play/colecao/<slug>
    name: str
    kind: str  # SHOWS or MOVIES


@dataclass(frozen=True)
class Channel:
    """A live TV or radio channel."""

    slug: str  # e.g. "rtp1", used to fetch the stream
    name: str
    kind: str  # TV or RADIO
    thumbnail: Optional[str] = None
    now_playing: Optional[str] = None


@dataclass(frozen=True)
class Program:
    id: int
    title: str
    thumbnail: Optional[str] = None


@dataclass(frozen=True)
class Season:
    """One season of a show. On RTP Play each season is a program of its own."""

    program_id: int
    title: str  # as shown on the site, e.g. "Temporada 2"
    number: Optional[int] = None


@dataclass(frozen=True)
class ProgramInfo:
    """Details from a program page. Fields the page lacks are None or empty."""

    program_id: int
    plot: Optional[str] = None
    image: Optional[str] = None  # landscape artwork
    year: Optional[int] = None
    seasons: List[Season] = field(default_factory=list)
    episode_path: Optional[str] = None  # latest episode; a film's only one


@dataclass(frozen=True)
class Episode:
    program_id: int
    id: int
    title: str
    path: str  # site path such as "/play/p1525/e892592/a-mosca", used to fetch the stream
    thumbnail: Optional[str] = None
    date: Optional[str] = None  # as shown on the site, e.g. "28 nov. 2025"


@dataclass(frozen=True)
class EpisodeInfo:
    """Details from an episode page that the episode lists leave out."""

    plot: Optional[str] = None
    duration: Optional[int] = None  # seconds
    image: Optional[str] = None


@dataclass(frozen=True)
class Stream:
    """A playable media URL plus the HTTP headers the CDN requires."""

    url: str
    protocol: str  # HLS, DASH or PROGRESSIVE
    headers: Dict[str, str] = field(default_factory=dict)
    is_live: bool = False


@dataclass(frozen=True)
class Page(Generic[T]):
    """One page of a paginated listing."""

    items: List[T]
    page: int
    has_more: bool
