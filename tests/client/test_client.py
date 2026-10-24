import pytest

from conftest import FakeResponse, FakeSession, load_fixture
from rtpplay import Cache, HttpClient, RateLimiter, RtpPlayClient
from rtpplay.client import CACHE_VERSION, CATEGORIES, COLLECTION_TTL, COLLECTIONS
from rtpplay.models import HLS, MOVIES, SHOWS


def make_client(*responses, cache=None):
    session = FakeSession(*responses)
    limiter = RateLimiter(rate=100, capacity=100, sleep=lambda s: None)
    return RtpPlayClient(HttpClient(session=session, limiter=limiter), cache), session


@pytest.fixture
def cache(clock):
    cache = Cache(clock=clock)
    yield cache
    cache.close()


def test_categories_need_no_request():
    client, session = make_client()
    categories = client.categories()
    assert len(categories) == len(CATEGORIES)
    assert len({c.id for c in categories}) == len(categories)
    assert session.requests == []


def test_programs_requests_the_category_alphabetically():
    client, session = make_client(FakeResponse(200, load_fixture("programs.html")))
    page = client.programs(9, page=2)
    request = session.requests[0]
    assert request["url"] == "https://www.rtp.pt/play/bg_l_pg/"
    assert request["params"] == {"listcategory": 9, "listtype": "az", "type": "all", "page": 2}
    assert page.page == 2
    assert [p.id for p in page.items] == [17251, 13632]


def test_short_page_is_the_last_one():
    client, _ = make_client(FakeResponse(200, load_fixture("programs.html")))
    assert client.programs(9).has_more is False


def test_full_page_has_more():
    articles = load_fixture("episodes.html") * 6  # 12 items, a full page
    client, _ = make_client(FakeResponse(200, articles))
    assert client.episodes(1525).has_more is True


def test_episodes_request():
    client, session = make_client(FakeResponse(200, load_fixture("episodes.html")))
    client.episodes(1525)
    assert session.requests[0]["params"] == {"listProgram": 1525, "type": "all", "page": 1}


def test_seasons_fetch_the_program_page():
    client, session = make_client(FakeResponse(200, load_fixture("program_seasons.html")))
    seasons = client.seasons(10209)
    assert session.requests[0]["url"] == "https://www.rtp.pt/play/p10209/"
    assert [s.program_id for s in seasons] == [10209, 5057]


def test_search_strips_the_query():
    client, session = make_client(FakeResponse(200, load_fixture("search.html")))
    client.search("  telejornal ")
    assert session.requests[0]["params"]["listQuery"] == "telejornal"


@pytest.mark.parametrize("call", [lambda c: c.search("  "), lambda c: c.programs(1, page=0)])
def test_invalid_arguments_fail_before_any_request(call):
    client, session = make_client()
    with pytest.raises(ValueError):
        call(client)
    assert session.requests == []


def test_live_stream_carries_the_headers_the_cdn_needs():
    client, session = make_client(FakeResponse(200, load_fixture("live_channel.html")))
    stream = client.live_stream("rtp1")
    assert session.requests[0]["url"] == "https://www.rtp.pt/play/direto/rtp1"
    assert set(stream.headers) == {"User-Agent", "Referer", "Origin"}
    assert stream.is_live


def test_episode_stream_fetches_the_episode_page():
    client, session = make_client(FakeResponse(200, load_fixture("episode_tv.html")))
    stream = client.episode_stream("/play/p1525/e892592/a-mosca")
    assert session.requests[0]["url"] == "https://www.rtp.pt/play/p1525/e892592/a-mosca"
    assert stream.headers["Referer"] == "https://www.rtp.pt/play/"


def test_fiction_episode_stream_is_hls():
    client, _ = make_client(FakeResponse(200, load_fixture("episode_fiction.html")))
    stream = client.episode_stream("/play/p10209/e763432/3-mulheres-pos-revolucao")
    assert stream.protocol == HLS
    assert stream.url.startswith("https://streaming-vod.rtp.pt/hls/")


def test_episode_stream_rejects_foreign_urls():
    client, session = make_client()
    with pytest.raises(ValueError):
        client.episode_stream("https://evil.example/play/x")
    assert session.requests == []


@pytest.mark.parametrize("slug", ["", "../bg_l_s/?listQuery=x", "rtp1/../x"])
def test_live_stream_rejects_invalid_slugs_before_any_request(slug):
    client, session = make_client()
    with pytest.raises(ValueError, match="channel_slug"):
        client.live_stream(slug)
    assert session.requests == []


def test_collections_need_no_request():
    client, session = make_client()
    assert {c.kind for c in client.collections(SHOWS)} == {SHOWS}
    assert {c.kind for c in client.collections(MOVIES)} == {MOVIES}
    assert len(client.collections(SHOWS)) + len(client.collections(MOVIES)) == len(COLLECTIONS)
    assert session.requests == []


def test_collection_is_split_into_pages():
    fifteen_programs = load_fixture("collection.html").replace("</div>", "") * 5  # 15 programs
    client, session = make_client(
        FakeResponse(200, fifteen_programs), FakeResponse(200, fifteen_programs)
    )
    first, second = client.collection("filmes"), client.collection("filmes", page=2)
    assert session.requests[0]["url"] == "https://www.rtp.pt/play/colecao/filmes"
    assert (len(first.items), first.has_more) == (12, True)
    assert (len(second.items), second.has_more) == (3, False)


def test_collection_is_cached(cache, clock):
    response = FakeResponse(200, load_fixture("collection.html"))
    client, session = make_client(response, response, cache=cache)
    assert client.collection("filmes") == client.collection("filmes")
    assert len(session.requests) == 1
    clock.now += COLLECTION_TTL
    client.collection("filmes")
    assert len(session.requests) == 2


@pytest.mark.parametrize(
    "call", [lambda c: c.collection("../p1"), lambda c: c.collection("filmes", 0)]
)
def test_invalid_collection_arguments_fail_before_any_request(call):
    client, session = make_client()
    with pytest.raises(ValueError):
        call(client)
    assert session.requests == []


def test_program_info_is_cached_and_shared_with_seasons(cache):
    client, session = make_client(
        FakeResponse(200, load_fixture("program_movie.html")), cache=cache
    )
    info = client.program_info(17296)
    assert session.requests[0]["url"] == "https://www.rtp.pt/play/p17296/"
    assert client.program_info(17296) == info
    assert client.seasons(17296) == []
    assert len(session.requests) == 1


def test_cached_seasons_keep_their_type(cache):
    response = FakeResponse(200, load_fixture("program_seasons.html"))
    client, session = make_client(response, cache=cache)
    assert client.seasons(10209) == client.seasons(10209)
    assert len(session.requests) == 1


def test_episode_info_is_cached(cache):
    client, session = make_client(FakeResponse(200, load_fixture("episode_info.html")), cache=cache)
    path = "/play/p17133/e953860/o-espiao-que-veio-do-futebol"
    assert client.episode_info(path) == client.episode_info(path)
    assert session.requests[0]["url"] == "https://www.rtp.pt" + path
    assert len(session.requests) == 1


def test_episode_info_rejects_foreign_urls():
    client, session = make_client()
    with pytest.raises(ValueError):
        client.episode_info("https://evil.example/play/x")
    assert session.requests == []


def test_cache_entries_that_no_longer_fit_the_model_are_refetched(cache):
    client, session = make_client(FakeResponse(200, load_fixture("episode_info.html")), cache=cache)
    path = "/play/p17133/e953860/o-espiao-que-veio-do-futebol"
    cache.set("v{}:episode:{}".format(CACHE_VERSION, path), {"renamed": 1}, ttl=60)
    assert client.episode_info(path).duration == 2706
    assert len(session.requests) == 1
    assert client.episode_info(path).duration == 2706  # and the fresh value replaced it
    assert len(session.requests) == 1
