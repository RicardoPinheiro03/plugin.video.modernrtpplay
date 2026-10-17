import pytest

from conftest import FakeResponse, FakeSession, load_fixture
from rtpplay import HttpClient, RateLimiter, RtpPlayClient
from rtpplay.client import CATEGORIES


def make_client(*responses):
    session = FakeSession(*responses)
    limiter = RateLimiter(rate=100, capacity=100, sleep=lambda s: None)
    return RtpPlayClient(HttpClient(session=session, limiter=limiter)), session


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


def test_episode_stream_rejects_foreign_urls():
    client, session = make_client()
    with pytest.raises(ValueError):
        client.episode_stream("https://evil.example/play/x")
    assert session.requests == []
