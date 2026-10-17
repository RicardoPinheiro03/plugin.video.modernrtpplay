"""Pure functions turning RTP Play HTML into model objects.

The site has no public JSON API, so this module is the one place that knows
about its markup. When RTP changes the website, fixes belong here (and in the
HTML fixtures under ``tests/client/fixtures``).
"""

from __future__ import annotations

import base64
import html
import json
import re
from typing import List, Optional
from urllib.parse import unquote

from .errors import ParseError
from .models import DASH, HLS, PROGRESSIVE, RADIO, TV, Channel, Episode, Program, Stream

_ARTICLE = re.compile(r"<article\b.*?</article>", re.S)
_EPISODE_LINK = re.compile(
    r'<a\s+href="(?P<path>/play/(?:[\w-]+/)?p(?P<program>\d+)/e(?P<episode>\d+)/[^"]*)"'
    r'\s+title="(?P<title>[^"]*)"'
)
_IMG = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"')
_EPISODE_TITLE = re.compile(r'<(?:p|h4) class="episode-title">(.*?)</(?:p|h4)>', re.S)
_EPISODE_LEAD = re.compile(r'<span class="episode-lead">(.*?)</span>', re.S)
_EPISODE_DATE = re.compile(r'<(?:div|span) class="episode-date">(.*?)</(?:div|span)>', re.S)

_CHANNEL = re.compile(
    r'<span id="(?P<kind>tv|radio)-\d+"[^>]*>\s*'
    r'<a\s+title="[^"]*"\s+href="/play/direto/(?P<slug>[\w-]+)".*?</a>',
    re.S,
)
_CHANNEL_NAME = re.compile(r'<img alt="Imagem de ([^"]+)"')
_CHANNEL_NOW = re.compile(r'<h4 class="ev-title-epg">(.*?)</h4>', re.S)

_LIVE_HLS = re.compile(r'\bhls_url\s*=\s*"([^"]+)"')

_PLAYER_FILE = re.compile(r'(?:\bvar\s+f\s*=|\bfile\s*:)\s*(\{[^}]*\}|"[^"]+")')
_OBFUSCATED = re.compile(
    r'atob\(\s*decodeURIComponent\(\s*(\[[^\]]*\])\s*\.join\(\s*(?:""|\'\')\s*\)\s*\)\s*\)'
)
_KEY_VALUE = re.compile(r'(\w+)\s*:\s*"([^"]*)"')

_ARTICLE_PREFIX = "Aceder a "


def parse_programs(fragment: str) -> List[Program]:
    """Parse a program list fragment (``/play/bg_l_pg/``).

    Each card links to the program's latest episode; we only keep the program.
    """
    programs = []
    for article in _ARTICLE.findall(fragment):
        link = _EPISODE_LINK.search(article)
        if not link:
            continue
        title = _first(_EPISODE_TITLE, article) or _strip_prefix(link.group("title"))
        programs.append(
            Program(id=int(link.group("program")), title=title, thumbnail=_first(_IMG, article))
        )
    return programs


def parse_episodes(fragment: str) -> List[Episode]:
    """Parse an episode list fragment (``/play/bg_l_ep/`` or ``/play/bg_l_s/``)."""
    episodes = []
    for article in _ARTICLE.findall(fragment):
        link = _EPISODE_LINK.search(article)
        if not link:
            continue
        # Search results split the title into program name and episode lead;
        # elsewhere the link title already reads "Program - Episode".
        lead = _first(_EPISODE_LEAD, article)
        title = _first(_EPISODE_TITLE, article)
        episodes.append(
            Episode(
                program_id=int(link.group("program")),
                id=int(link.group("episode")),
                title=_join_title(title, lead) or _strip_prefix(link.group("title")),
                path=link.group("path"),
                thumbnail=_first(_IMG, article),
                date=_first(_EPISODE_DATE, article),
            )
        )
    return episodes


def parse_live_channels(page: str) -> List[Channel]:
    """Parse the live page (``/play/direto``)."""
    channels = []
    for match in _CHANNEL.finditer(page):
        block = match.group(0)
        name = _first(_CHANNEL_NAME, block) or match.group("slug")
        channels.append(
            Channel(
                slug=match.group("slug"),
                name=name,
                kind=TV if match.group("kind") == "tv" else RADIO,
                thumbnail=_absolute(_first(_IMG, block)),
                now_playing=_first(_CHANNEL_NOW, block),
            )
        )
    if not channels:
        raise ParseError("No live channels found on the live page")
    return channels


def parse_live_stream(page: str) -> Stream:
    """Extract the HLS URL from a live channel page (``/play/direto/<slug>``)."""
    match = _LIVE_HLS.search(page)
    if not match:
        raise ParseError("No live stream found on the channel page")
    return Stream(url=match.group(1), protocol=HLS, is_live=True)


def parse_episode_stream(page: str) -> Stream:
    """Extract the media URL from an episode page.

    Pages contain several player configurations (older ones are commented
    out); the active one is the last. URLs are often obfuscated as
    ``atob(decodeURIComponent([...].join("")))``.
    """
    candidates = _PLAYER_FILE.findall(page)
    if not candidates:
        raise ParseError("No player configuration found on the episode page")
    source = _deobfuscate(candidates[-1])

    if source.startswith('"'):
        url = _clean_media_url(source.strip('"'))
        if url:
            return Stream(url=url, protocol=_protocol_of(url))
    else:
        urls = dict(_KEY_VALUE.findall(source))
        for key, protocol in ((HLS, HLS), (DASH, DASH)):
            url = _clean_media_url(urls.get(key, ""))
            if url:
                return Stream(url=url, protocol=protocol)
    raise ParseError("Player configuration has no playable URL")


def _deobfuscate(source: str) -> str:
    def decode(match: "re.Match[str]") -> str:
        parts = json.loads(match.group(1).replace("'", '"'))
        return json.dumps(base64.b64decode(unquote("".join(parts))).decode("utf-8"))

    return _OBFUSCATED.sub(decode, source)


def _clean_media_url(url: str) -> Optional[str]:
    if not url.startswith("http"):
        return None
    # streaming-ondemand serves legacy manifests that no longer play.
    if "//streaming-ondemand.rtp.pt/" in url:
        return None
    # The FairPlay/Widevine paths serve the same clear content under /hls/ and /dash/.
    return url.replace("/drm-fps/", "/hls/").replace("/drm-dash/", "/dash/")


def _protocol_of(url: str) -> str:
    path = url.split("?", 1)[0]
    if path.endswith(".m3u8"):
        return HLS
    if path.endswith(".mpd"):
        return DASH
    return PROGRESSIVE


def _first(pattern: "re.Pattern[str]", text: str) -> Optional[str]:
    match = pattern.search(text)
    if not match:
        return None
    return _clean_text(match.group(1)) or None


def _join_title(title: Optional[str], lead: Optional[str]) -> Optional[str]:
    return "{} - {}".format(title, lead) if title and lead else None


def _clean_text(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text)).split())


def _strip_prefix(title: str) -> str:
    title = _clean_text(title)
    return title[len(_ARTICLE_PREFIX) :] if title.startswith(_ARTICLE_PREFIX) else title


def _absolute(url: Optional[str]) -> Optional[str]:
    return "https:" + url if url and url.startswith("//") else url
