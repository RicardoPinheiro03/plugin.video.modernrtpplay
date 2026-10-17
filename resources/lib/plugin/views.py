"""Directory listings and playback, one method per plugin action."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from rtpplay import Page, RateLimitedError, RtpPlayClient, RtpPlayError, Stream
from rtpplay.models import DASH, HLS, RADIO

from .routing import Request, build_url

log = logging.getLogger(__name__)

# Localized string ids (resources/language/*/strings.po).
LIVE = 30000
PROGRAMS = 30001
SEARCH = 30002
NEXT_PAGE = 30003
RATE_LIMITED_RETRY_IN = 30004
RATE_LIMITED = 30005
LOAD_FAILED = 30006
SEARCH_HEADING = 30007

ISA = "inputstream.adaptive"
MIME_TYPES = {HLS: "application/vnd.apple.mpegurl", DASH: "application/dash+xml"}

DirectoryItem = Tuple[str, xbmcgui.ListItem, bool]


class Addon:
    def __init__(self, client: RtpPlayClient, request: Request) -> None:
        self._client = client
        self._request = request
        self._handle = request.handle
        self._addon = xbmcaddon.Addon()

    def dispatch(self) -> None:
        params = self._request.params
        actions: Dict[str, Callable[[], None]] = {
            "root": self.root,
            "live": self.live,
            "categories": self.categories,
            "programs": lambda: self.programs(int(params["category"]), _page(params)),
            "episodes": lambda: self.episodes(int(params["program"]), _page(params)),
            "search": lambda: self.search(params.get("query"), _page(params)),
            "play_live": lambda: self.play_live(params["channel"]),
            "play_episode": lambda: self.play_episode(params["path"]),
        }
        action = params.get("action", "root")
        if action not in actions:
            log.error("Unknown action %r", action)
            return
        try:
            actions[action]()
        except RtpPlayError as error:
            self._fail(action, error)

    # --- Listings ---------------------------------------------------------

    def root(self) -> None:
        self._directory(
            [
                self._folder(self._string(LIVE), "live"),
                self._folder(self._string(PROGRAMS), "categories"),
                self._folder(self._string(SEARCH), "search"),
            ]
        )

    def live(self) -> None:
        items = []
        for channel in self._client.live_channels():
            label = channel.name
            if channel.now_playing:
                label = "{} - {}".format(channel.name, channel.now_playing)
            item = self._playable(
                label, channel.thumbnail, media="music" if channel.kind == RADIO else "video"
            )
            items.append((self._url("play_live", channel=channel.slug), item, False))
        self._directory(items, content="videos", cache=False)

    def categories(self) -> None:
        self._directory(
            [self._folder(c.name, "programs", category=c.id) for c in self._client.categories()]
        )

    def programs(self, category_id: int, page: int) -> None:
        result = self._client.programs(category_id, page)
        items = [
            self._folder(p.title, "episodes", thumbnail=p.thumbnail, program=p.id)
            for p in result.items
        ]
        self._directory(self._with_next(items, result, "programs", category=category_id), "tvshows")

    def episodes(self, program_id: int, page: int) -> None:
        result = self._client.episodes(program_id, page)
        self._directory(
            self._with_next(self._episode_items(result), result, "episodes", program=program_id),
            "episodes",
        )

    def search(self, query: Optional[str], page: int) -> None:
        if not query:
            query = xbmcgui.Dialog().input(self._string(SEARCH_HEADING))
            if not query:
                xbmcplugin.endOfDirectory(self._handle, succeeded=False)
                return
        result = self._client.search(query, page)
        self._directory(
            self._with_next(self._episode_items(result), result, "search", query=query),
            "episodes",
            cache=False,
        )

    # --- Playback ---------------------------------------------------------

    def play_live(self, channel_slug: str) -> None:
        self._resolve(self._client.live_stream(channel_slug))

    def play_episode(self, path: str) -> None:
        self._resolve(self._client.episode_stream(path))

    def _resolve(self, stream: Stream) -> None:
        headers = urlencode(stream.headers)
        item = xbmcgui.ListItem(path="{}|{}".format(stream.url, headers), offscreen=True)
        item.setContentLookup(False)
        if stream.protocol in MIME_TYPES:
            item.setMimeType(MIME_TYPES[stream.protocol])
            if xbmc.getCondVisibility("System.HasAddon({})".format(ISA)):
                item.setProperty("inputstream", ISA)
                item.setProperty(ISA + ".manifest_headers", headers)
                item.setProperty(ISA + ".stream_headers", headers)
        xbmcplugin.setResolvedUrl(self._handle, True, item)

    # --- Helpers ----------------------------------------------------------

    def _episode_items(self, page: Page) -> List[DirectoryItem]:
        items = []
        for episode in page.items:
            item = self._playable(episode.title, episode.thumbnail, plot=episode.date)
            items.append((self._url("play_episode", path=episode.path), item, False))
        return items

    def _with_next(self, items: List[DirectoryItem], page: Page, action: str, **params: object):
        if page.has_more:
            items.append(
                self._folder(self._string(NEXT_PAGE), action, page=page.page + 1, **params)
            )
        return items

    def _folder(self, label: str, action: str, thumbnail: Optional[str] = None, **params: object):
        item = xbmcgui.ListItem(label, offscreen=True)
        if thumbnail:
            item.setArt({"thumb": thumbnail, "poster": thumbnail})
        return self._url(action, **params), item, True

    @staticmethod
    def _playable(
        label: str, thumbnail: Optional[str], plot: Optional[str] = None, media: str = "video"
    ):
        item = xbmcgui.ListItem(label, offscreen=True)
        item.setProperty("IsPlayable", "true")
        if thumbnail:
            item.setArt({"thumb": thumbnail, "icon": thumbnail})
        if media == "video":
            tag = item.getVideoInfoTag()
            tag.setTitle(label)
            if plot:
                tag.setPlot(plot)
        else:
            item.getMusicInfoTag().setTitle(label)
        return item

    def _directory(self, items: List[DirectoryItem], content: str = "", cache: bool = True) -> None:
        if content:
            xbmcplugin.setContent(self._handle, content)
        xbmcplugin.addDirectoryItems(self._handle, items, len(items))
        xbmcplugin.endOfDirectory(self._handle, succeeded=True, cacheToDisc=cache)

    def _url(self, action: str, **params: object) -> str:
        return build_url(self._request.base_url, action, **params)

    def _string(self, string_id: int) -> str:
        return self._addon.getLocalizedString(string_id)

    def _fail(self, action: str, error: RtpPlayError) -> None:
        log.error("Action %s failed: %s", action, error)
        if isinstance(error, RateLimitedError):
            if error.retry_after:
                message = self._string(RATE_LIMITED_RETRY_IN) % int(error.retry_after)
            else:
                message = self._string(RATE_LIMITED)
        else:
            message = self._string(LOAD_FAILED)
        xbmcgui.Dialog().notification(
            self._addon.getAddonInfo("name"), message, xbmcgui.NOTIFICATION_ERROR
        )
        if action.startswith("play_"):
            xbmcplugin.setResolvedUrl(self._handle, False, xbmcgui.ListItem(offscreen=True))
        else:
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)


def _page(params: Dict[str, str]) -> int:
    return max(1, int(params.get("page", 1)))
