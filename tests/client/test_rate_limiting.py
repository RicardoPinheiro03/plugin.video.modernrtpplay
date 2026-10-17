"""Rate limiting: our own request budget and how we react when RTP Play throttles us."""

import email.utils

import pytest
import requests

from conftest import FakeResponse, FakeSession
from rtpplay import HttpClient, NetworkError, RateLimitedError, RateLimiter, RetryPolicy
from rtpplay.errors import NotFoundError, RtpPlayError
from rtpplay.http import parse_retry_after

OK = FakeResponse(200, "ok")


def make_client(session, clock, retry=None, rand=lambda: 1.0):
    # Big bucket so these tests only exercise retry behaviour.
    limiter = RateLimiter(rate=100, capacity=100, clock=clock, sleep=clock.sleep)
    return HttpClient(
        session=session, limiter=limiter, retry=retry, sleep=clock.sleep, rand=rand, now=clock
    )


# --- RateLimiter (client side) ---------------------------------------------


def test_limiter_allows_a_burst_up_to_capacity_without_sleeping(clock):
    limiter = RateLimiter(rate=2, capacity=3, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        limiter.acquire()
    assert clock.sleeps == []


def test_limiter_spaces_requests_once_the_burst_is_spent(clock):
    limiter = RateLimiter(rate=2, capacity=1, clock=clock, sleep=clock.sleep)
    for _ in range(4):
        limiter.acquire()
    assert clock.sleeps == pytest.approx([0.5, 0.5, 0.5])


def test_limiter_refills_while_idle(clock):
    limiter = RateLimiter(rate=1, capacity=2, clock=clock, sleep=clock.sleep)
    limiter.acquire()
    limiter.acquire()
    clock.now += 10  # idle long enough to refill, but never above capacity
    limiter.acquire()
    limiter.acquire()
    assert clock.sleeps == []
    limiter.acquire()
    assert clock.sleeps == pytest.approx([1.0])


def test_limiter_is_applied_to_every_http_request(clock):
    session = FakeSession(OK, OK, OK)
    limiter = RateLimiter(rate=1, capacity=1, clock=clock, sleep=clock.sleep)
    http = HttpClient(session=session, limiter=limiter, sleep=clock.sleep, now=clock)
    for _ in range(3):
        http.get_text("/play/")
    assert clock.sleeps == pytest.approx([1.0, 1.0])


@pytest.mark.parametrize("rate, capacity", [(0, 1), (-1, 1), (1, 0)])
def test_limiter_rejects_invalid_configuration(rate, capacity):
    with pytest.raises(ValueError):
        RateLimiter(rate=rate, capacity=capacity)


# --- Server-side throttling (HTTP 429) -------------------------------------


def test_429_with_retry_after_seconds_waits_that_long_then_succeeds(clock):
    session = FakeSession(FakeResponse(429, headers={"Retry-After": "7"}), OK)
    assert make_client(session, clock).get_text("/play/") == "ok"
    assert clock.sleeps == [7.0]
    assert len(session.requests) == 2


def test_429_with_retry_after_http_date_is_honoured(clock):
    clock.now = 1_700_000_000.0
    date = email.utils.formatdate(clock.now + 5, usegmt=True)
    session = FakeSession(FakeResponse(429, headers={"Retry-After": date}), OK)
    make_client(session, clock).get_text("/play/")
    assert clock.sleeps == pytest.approx([5.0])


def test_429_without_retry_after_uses_exponential_backoff(clock):
    session = FakeSession(FakeResponse(429), FakeResponse(429), FakeResponse(429), OK)
    make_client(session, clock, RetryPolicy(max_retries=3, backoff_base=1)).get_text("/play/")
    assert clock.sleeps == [1.0, 2.0, 4.0]


def test_backoff_uses_full_jitter(clock):
    session = FakeSession(FakeResponse(429), FakeResponse(429), OK)
    make_client(session, clock, RetryPolicy(backoff_base=2), rand=lambda: 0.25).get_text("/play/")
    assert clock.sleeps == [0.5, 1.0]


def test_backoff_is_capped(clock):
    session = FakeSession(*[FakeResponse(429)] * 4, OK)
    policy = RetryPolicy(max_retries=4, backoff_base=4, max_backoff=10)
    make_client(session, clock, policy).get_text("/play/")
    assert clock.sleeps == [4.0, 8.0, 10.0, 10.0]


def test_persistent_429_raises_rate_limited_error_after_max_retries(clock):
    session = FakeSession(*[FakeResponse(429, headers={"Retry-After": "2"})] * 3)
    with pytest.raises(RateLimitedError) as error:
        make_client(session, clock, RetryPolicy(max_retries=2)).get_text("/play/")
    assert error.value.retry_after == 2.0
    assert len(session.requests) == 3
    assert clock.sleeps == [2.0, 2.0]


def test_retry_after_longer_than_allowed_fails_fast_instead_of_blocking_kodi(clock):
    session = FakeSession(FakeResponse(429, headers={"Retry-After": "3600"}))
    with pytest.raises(RateLimitedError) as error:
        make_client(session, clock, RetryPolicy(max_retry_after=30)).get_text("/play/")
    assert error.value.retry_after == 3600.0
    assert clock.sleeps == []


def test_rate_limited_error_is_an_rtpplay_error():
    assert issubclass(RateLimitedError, RtpPlayError)


# --- Other transient failures ----------------------------------------------


@pytest.mark.parametrize("status", [502, 503, 504])
def test_transient_server_errors_are_retried(clock, status):
    session = FakeSession(FakeResponse(status), OK)
    assert make_client(session, clock).get_text("/play/") == "ok"
    assert len(session.requests) == 2


def test_503_honours_retry_after(clock):
    session = FakeSession(FakeResponse(503, headers={"Retry-After": "3"}), OK)
    make_client(session, clock).get_text("/play/")
    assert clock.sleeps == [3.0]


def test_persistent_503_raises_network_error(clock):
    session = FakeSession(*[FakeResponse(503)] * 2)
    with pytest.raises(NetworkError):
        make_client(session, clock, RetryPolicy(max_retries=1)).get_text("/play/")


@pytest.mark.parametrize("exc", [requests.ConnectionError("boom"), requests.Timeout("slow")])
def test_connection_failures_are_retried_with_backoff(clock, exc):
    session = FakeSession(exc, OK)
    assert make_client(session, clock).get_text("/play/") == "ok"
    assert clock.sleeps == [1.0]


def test_persistent_connection_failure_raises_network_error(clock):
    session = FakeSession(*[requests.ConnectionError("down")] * 3)
    with pytest.raises(NetworkError):
        make_client(session, clock, RetryPolicy(max_retries=2)).get_text("/play/")
    assert len(session.requests) == 3


def test_404_is_not_retried(clock):
    session = FakeSession(FakeResponse(404))
    with pytest.raises(NotFoundError):
        make_client(session, clock).get_text("/play/p1/e1/x")
    assert len(session.requests) == 1
    assert clock.sleeps == []


def test_unexpected_status_is_not_retried(clock):
    session = FakeSession(FakeResponse(500))
    with pytest.raises(RtpPlayError):
        make_client(session, clock).get_text("/play/")
    assert len(session.requests) == 1


# --- parse_retry_after -------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "soon", "-5"])
def test_parse_retry_after_ignores_missing_or_invalid_values(value):
    assert parse_retry_after(value) is None


def test_parse_retry_after_clamps_past_dates_to_zero():
    past = email.utils.formatdate(0, usegmt=True)
    assert parse_retry_after(past, now=lambda: 1_700_000_000.0) == 0.0
