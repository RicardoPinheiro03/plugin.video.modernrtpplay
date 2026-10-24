from urllib.parse import parse_qsl, urlparse

import pytest

from plugin.routing import Request, build_url, parse_argv
from plugin.views import Addon, _fetch_some
from rtpplay import (
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
from rtpplay.errors import NetworkError, RateLimitedError
from rtpplay.models import HLS, MOVIES, PROGRESSIVE, RADIO, SHOWS, TV

BASE = "plugin://plugin.video.modernrtpplay/"
HEADERS = {"User-Agent": "UA", "Referer": "https://www.rtp.pt/play/"}


class FakeClient:
    def __init__(self, error=None, seasons=(), details_error=None):
        self.error = error
        self.details_error = details_error
        self.calls = []
        self._seasons = list(seasons)

    def _call(self, name, *args):
        self.calls.append((name,) + args)
        if self.error:
            raise self.error

    def categories(self):
        self._call("categories")
        return [Category(9, "ficcao", "Ficção")]

    def live_channels(self):
        self._call("live_channels")
        return [
            Channel("rtp1", "RTP1", TV, "https://img/rtp1.png", "Telejornal"),
            Channel("antena1", "Antena 1", RADIO),
        ]

    def collections(self, kind):
        self._call("collections", kind)
        return {
            SHOWS: [Collection("series-nacionais", "Séries Nacionais", SHOWS)],
            MOVIES: [Collection("filmes", "Cinema Internacional", MOVIES)],
        }[kind]

    def collection(self, slug, page):
        self._call("collection", slug, page)
        programs = [Program(17296, "Beleza Colateral", "https://img/poster.jpg"), Program(2, "B")]
        return Page(programs, page, has_more=True)

    def program_info(self, program_id):
        self._call("program_info", program_id)
        if self.details_error:
            raise self.details_error
        return ProgramInfo(
            program_id, "Howard...", "https://img/fanart.jpg", 2016, [], "/play/p17296/e961379/x"
        )

    def episode_info(self, path):
        self._call("episode_info", path)
        if self.details_error:
            raise self.details_error
        return EpisodeInfo("1941. Cândido...", 2706, "https://img/show.jpg")

    def programs(self, category_id, page):
        self._call("programs", category_id, page)
        return Page([Program(1525, "A Mosca", "https://img/p.jpg")], page, has_more=True)

    def seasons(self, program_id):
        self._call("seasons", program_id)
        return self._seasons

    def episodes(self, program_id, page):
        self._call("episodes", program_id, page)
        episode = Episode(1525, 892592, "A Mosca - Pausa", "/play/p1525/e892592/a-mosca")
        return Page([episode], page, has_more=False)

    def search(self, query, page):
        self._call("search", query, page)
        return Page([], page, has_more=False)

    def live_stream(self, slug):
        self._call("live_stream", slug)
        return Stream("https://live/rtp1.m3u8", HLS, dict(HEADERS), is_live=True)

    def episode_stream(self, path, best_quality=True):
        self._call("episode_stream", path, best_quality)
        return Stream("https://cdn/a.mp3", PROGRESSIVE, dict(HEADERS))


def run(client, **params):
    Addon(client, Request(BASE, 1, {k: str(v) for k, v in params.items()})).dispatch()


def params_of(url):
    return dict(parse_qsl(urlparse(url).query))


def test_parse_argv_and_build_url_round_trip():
    url = build_url(BASE, "programs", category=9, page=2, skipped=None)
    request = parse_argv([BASE, "7", "?" + urlparse(url).query])
    assert request == Request(BASE, 7, {"action": "programs", "category": "9", "page": "2"})


def test_parse_argv_without_query():
    assert parse_argv([BASE, "3", ""]).params == {}


def test_root_menu(kodi):
    run(FakeClient())
    assert [params_of(url) for url, _, _ in kodi.items] == [
        {"action": "collections", "kind": "shows"},
        {"action": "collections", "kind": "movies"},
        {"action": "categories"},
        {"action": "search"},
    ]
    assert all(is_folder for _, _, is_folder in kodi.items)
    assert kodi.end["succeeded"]


def test_live_lists_playable_channels(kodi):
    run(FakeClient(), action="live")
    (url, tv, folder), (_, radio, _) = kodi.items
    assert params_of(url) == {"action": "play_live", "channel": "rtp1"}
    assert not folder
    assert tv.label == "RTP1 - Telejornal"
    assert tv.properties["IsPlayable"] == "true"
    assert tv.art["thumb"] == "https://img/rtp1.png"
    assert radio.music_tag.title == "Antena 1"
    assert kodi.end["cache"] is False  # "now playing" changes, never cache it


def test_categories_link_to_programs(kodi):
    run(FakeClient(), action="categories")
    assert params_of(kodi.items[0][0]) == {"action": "programs", "category": "9"}


def test_programs_adds_next_page_when_there_is_more(kodi):
    client = FakeClient()
    run(client, action="programs", category=9, page=2)
    assert client.calls == [("programs", 9, 2)]
    assert params_of(kodi.items[0][0]) == {"action": "seasons", "program": "1525"}
    assert params_of(kodi.items[-1][0]) == {"action": "programs", "category": "9", "page": "3"}
    assert kodi.content == "tvshows"


def test_seasons_list_each_season_as_a_folder(kodi):
    client = FakeClient(seasons=[Season(10209, "Temporada 2", 2), Season(1, "Especial")])
    run(client, action="seasons", program=10209)
    assert client.calls == [("seasons", 10209)]
    assert [item.label for _, item, _ in kodi.items] == ["Season 2", "Especial"]
    assert params_of(kodi.items[0][0]) == {"action": "episodes", "program": "10209"}
    assert all(folder for _, _, folder in kodi.items)
    assert kodi.content == "seasons"


@pytest.mark.parametrize("seasons, listed", [([], 1525), ([Season(1600, "Temporada 1", 1)], 1600)])
def test_single_season_programs_go_straight_to_episodes(kodi, seasons, listed):
    client = FakeClient(seasons=seasons)
    run(client, action="seasons", program=1525)
    assert client.calls[:2] == [("seasons", 1525), ("episodes", listed, 1)]
    assert params_of(kodi.items[0][0])["action"] == "play_episode"
    assert kodi.content == "episodes"


def test_episodes_without_more_pages_has_no_next_item(kodi):
    run(FakeClient(), action="episodes", program=1525)
    assert len(kodi.items) == 1
    url, item, folder = kodi.items[0]
    assert params_of(url) == {"action": "play_episode", "path": "/play/p1525/e892592/a-mosca"}
    assert item.video_tag.title == "A Mosca - Pausa"


def test_episodes_show_their_synopsis_and_duration(kodi):
    client = FakeClient()
    run(client, action="episodes", program=1525)
    assert ("episode_info", "/play/p1525/e892592/a-mosca") in client.calls
    tag = kodi.items[0][1].video_tag
    assert (tag.plot, tag.duration, tag.media_type) == ("1941. Cândido...", 2706, "episode")


def test_episodes_still_list_when_details_fail(kodi):
    run(FakeClient(details_error=RateLimitedError("slow down")), action="episodes", program=1)
    assert kodi.end["succeeded"]
    assert kodi.items[0][1].video_tag.plot is None  # the fake episode has no date either
    assert kodi.notifications == []


def test_search_does_not_fetch_episode_details(kodi):
    client = FakeClient()
    client.search = lambda query, page: client.episodes(1, page)
    run(client, action="search", query="x")
    assert not any(call[0] == "episode_info" for call in client.calls)


@pytest.mark.parametrize(
    "kind, label", [("shows", "Séries Nacionais"), ("movies", "Cinema Internacional")]
)
def test_collections_list_one_folder_per_collection(kodi, kind, label):
    run(FakeClient(), action="collections", kind=kind)
    ((url, item, folder),) = kodi.items
    assert item.label == label and folder
    assert params_of(url)["action"] == "collection"


def test_movie_collection_lists_playable_films_with_details(kodi):
    client = FakeClient()
    run(client, action="collection", slug="filmes")
    url, item, folder = kodi.items[0]
    assert params_of(url) == {"action": "play_program", "program": "17296"}
    assert not folder and item.properties["IsPlayable"] == "true"
    tag = item.video_tag
    assert (tag.title, tag.plot, tag.year, tag.media_type) == (
        "Beleza Colateral",
        "Howard...",
        2016,
        "movie",
    )
    assert item.art["poster"] == "https://img/poster.jpg"
    assert item.art["fanart"] == "https://img/fanart.jpg"
    assert params_of(kodi.items[-1][0]) == {"action": "collection", "slug": "filmes", "page": "2"}
    assert kodi.content == "movies"


def test_show_collection_lists_shows_that_open_their_seasons(kodi):
    run(FakeClient(), action="collection", slug="series-nacionais")
    url, item, folder = kodi.items[0]
    assert params_of(url) == {"action": "seasons", "program": "17296"}
    assert folder
    assert item.video_tag.media_type == "tvshow"
    assert kodi.content == "tvshows"


def test_collection_stops_fetching_details_after_a_failure(kodi):
    client = FakeClient(details_error=NetworkError("down"))
    run(client, action="collection", slug="filmes")
    assert [c for c in client.calls if c[0] == "program_info"] == [("program_info", 17296)]
    assert len(kodi.items) == 3  # two films and the next page
    assert kodi.items[0][1].video_tag.plot is None


def test_play_program_plays_its_episode_without_checking_for_1080p(kodi):
    client = FakeClient()
    run(client, action="play_program", program=17296)
    assert ("episode_stream", "/play/p17296/e961379/x", False) in client.calls
    assert kodi.resolved[0] is True


def test_play_program_without_episode_fails_cleanly(kodi):
    client = FakeClient()
    client.program_info = lambda program_id: ProgramInfo(program_id)
    run(client, action="play_program", program=1)
    assert kodi.resolved[0] is False
    assert kodi.notifications == [("RTP Play", "Load failed")]


def test_search_prompts_for_a_query(kodi):
    client = FakeClient()
    kodi.input_text = "telejornal"
    run(client, action="search")
    assert client.calls == [("search", "telejornal", 1)]
    assert kodi.end == {"succeeded": True, "cache": False}


def test_cancelled_search_does_not_hit_the_site(kodi):
    client = FakeClient()
    run(client, action="search")
    assert client.calls == []
    assert kodi.end["succeeded"] is False


def test_play_hls_uses_inputstream_adaptive(kodi):
    run(FakeClient(), action="play_live", channel="rtp1")
    succeeded, item = kodi.resolved
    assert succeeded
    assert item.path.startswith("https://live/rtp1.m3u8|")
    assert "Referer=https%3A%2F%2Fwww.rtp.pt%2Fplay%2F" in item.path
    assert item.properties["inputstream"] == "inputstream.adaptive"
    assert item.properties["inputstream.adaptive.stream_headers"] == item.path.split("|", 1)[1]
    assert item.mime_type == "application/vnd.apple.mpegurl"
    assert item.content_lookup is False


def test_play_episode_asks_for_the_best_quality(kodi):
    client = FakeClient()
    run(client, action="play_episode", path="/play/p1/e2/x")
    assert client.calls == [("episode_stream", "/play/p1/e2/x", True)]


def test_play_progressive_audio(kodi):
    run(FakeClient(), action="play_episode", path="/play/p1/e2/x")
    _, item = kodi.resolved
    assert item.path.startswith("https://cdn/a.mp3|")
    assert "inputstream" not in item.properties


def test_rate_limit_with_retry_after_shows_wait_time(kodi):
    run(FakeClient(RateLimitedError("slow down", retry_after=42)), action="live")
    assert kodi.notifications == [("RTP Play", "Rate limited, retry in 42 s")]
    assert kodi.end["succeeded"] is False


def test_rate_limit_without_retry_after(kodi):
    run(FakeClient(RateLimitedError("slow down")), action="categories")
    assert kodi.notifications == [("RTP Play", "Rate limited")]


def test_failed_playback_is_reported_to_kodi(kodi):
    run(FakeClient(NetworkError("down")), action="play_live", channel="rtp1")
    assert kodi.notifications == [("RTP Play", "Load failed")]
    assert kodi.resolved[0] is False


def test_unknown_action_is_ignored_but_still_ends_the_directory(kodi):
    client = FakeClient()
    run(client, action="nope")
    assert client.calls == []
    assert kodi.items == []
    assert kodi.end["succeeded"] is False


@pytest.mark.parametrize(
    "params",
    [
        {"action": "programs", "category": "9", "page": "abc"},
        {"action": "programs"},
        {"action": "episodes", "program": "x"},
    ],
)
def test_malformed_parameters_fail_cleanly(kodi, params):
    run(FakeClient(), **params)
    assert kodi.notifications == [("RTP Play", "Load failed")]
    assert kodi.end["succeeded"] is False


def test_unexpected_errors_still_end_the_directory(kodi):
    run(FakeClient(KeyError("bug")), action="live")
    assert kodi.notifications == [("RTP Play", "Load failed")]
    assert kodi.end["succeeded"] is False


def test_unexpected_errors_during_playback_still_resolve(kodi):
    run(FakeClient(TypeError("bug")), action="play_live", channel="rtp1")
    assert kodi.resolved[0] is False


def test_stream_headers_encode_spaces_as_percent_20(kodi):
    client = FakeClient()
    client.live_stream = lambda slug: Stream(
        "https://live/x.m3u8", HLS, {"User-Agent": "Mozilla/5.0 (X11; Linux)"}
    )
    run(client, action="play_live", channel="rtp1")
    _, item = kodi.resolved
    assert item.path.endswith("|User-Agent=Mozilla%2F5.0%20%28X11%3B%20Linux%29")
    assert "+" not in item.properties["inputstream.adaptive.manifest_headers"]


@pytest.mark.parametrize("page, expected", [("0", 1), ("-3", 1), ("4", 4)])
def test_page_is_clamped_to_one(kodi, page, expected):
    client = FakeClient()
    run(client, action="episodes", program=1, page=page)
    assert client.calls[0] == ("episodes", 1, expected)


def test_details_stop_once_the_time_budget_is_spent():
    now = [0.0]

    def fetch(key):
        now[0] += 4  # each request takes 4 s
        return key * 10

    details = _fetch_some(fetch, [1, 2, 3, 4], clock=lambda: now[0])
    assert details == {1: 10, 2: 20, 3: 30}  # the 4th would start after 12 s > 10 s
