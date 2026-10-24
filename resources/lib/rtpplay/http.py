"""HTTP transport with client-side rate limiting and polite retries.

RTP Play is a public website, not an API built for third parties, so we:

* cap our own request rate with a token bucket (:class:`RateLimiter`), and
* back off when the server pushes back (HTTP 429 / 5xx), honouring
  ``Retry-After`` when it is sent (:class:`RetryPolicy`).

Time and randomness are injected so all of this is unit-testable without
real sleeping.
"""

from __future__ import annotations

import email.utils
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import timezone
from typing import Callable, Mapping, Optional, Union

import requests

from .errors import NetworkError, NotFoundError, RateLimitedError, RtpPlayError

log = logging.getLogger(__name__)

BASE_URL = "https://www.rtp.pt"

# The site and its CDN reject requests that do not look like a browser.
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/play/",
    "Origin": BASE_URL,
}

# exists() runs while Kodi waits to start playback, so a slow answer counts as a miss.
PROBE_TIMEOUT = 5.0

RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
# A truncated chunked body is as transient as a dropped connection.
RETRYABLE_ERRORS = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


class RateLimiter:
    """Token bucket: allows bursts of ``capacity`` requests, then ``rate`` per second."""

    def __init__(
        self,
        rate: float = 2.0,
        capacity: int = 4,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate <= 0 or capacity < 1:
            raise ValueError("rate must be > 0 and capacity >= 1")
        self.rate = rate
        self.capacity = capacity
        self._clock = clock
        self._sleep = sleep
        self._tokens = float(capacity)
        self._updated = clock()

    def acquire(self) -> None:
        """Block until a request may be sent."""
        self._refill()
        if self._tokens < 1:
            self._sleep((1 - self._tokens) / self.rate)
            self._refill()
        self._tokens -= 1

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
        self._updated = now


@dataclass(frozen=True)
class RetryPolicy:
    """How to react to transient failures.

    Delays grow as ``backoff_base * 2**attempt`` (capped at ``max_backoff``)
    with full jitter. A server-provided ``Retry-After`` replaces the computed
    delay; if it is longer than ``max_retry_after`` we give up immediately,
    because blocking Kodi's UI for minutes is worse than showing an error.
    For the same reason all waits of one request together stay within
    ``max_total_wait``: we give up rather than start a wait that would exceed it.
    """

    max_retries: int = 3
    backoff_base: float = 1.0
    max_backoff: float = 30.0
    max_retry_after: float = 30.0
    max_total_wait: float = 30.0

    def backoff(self, attempt: int, rand: Callable[[], float]) -> float:
        return min(self.max_backoff, self.backoff_base * (2**attempt)) * rand()


def parse_retry_after(
    value: Optional[str], now: Callable[[], float] = time.time
) -> Optional[float]:
    """Parse a ``Retry-After`` header (delta-seconds or HTTP-date) into seconds."""
    if not value:
        return None
    value = value.strip()
    # str.isdigit() also accepts non-ASCII digits such as "²", which float() rejects.
    if re.fullmatch(r"[0-9]+", value):
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:  # "-0000" zone: UTC, but parsed as naive (local) time
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, when.timestamp() - now())


class HttpClient:
    """Fetches pages from www.rtp.pt.

    ``session`` only needs a ``requests.Session``-compatible ``get`` method,
    so tests can pass a fake.
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        limiter: Optional[RateLimiter] = None,
        retry: Optional[RetryPolicy] = None,
        timeout: float = 15.0,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._session = session or requests.Session()
        self._limiter = limiter or RateLimiter(sleep=sleep)
        self._retry = retry or RetryPolicy()
        self._timeout = timeout
        self._sleep = sleep
        self._rand = rand
        self._now = now

    def get_text(self, path: str, params: Optional[Mapping[str, Union[str, int]]] = None) -> str:
        """GET ``path`` (relative to www.rtp.pt) and return the response body."""
        url = path if path.startswith("http") else BASE_URL + path
        attempt = 0
        waited = 0.0
        while True:
            self._limiter.acquire()
            try:
                response = self._session.get(
                    url, params=params, headers=DEFAULT_HEADERS, timeout=self._timeout
                )
            except RETRYABLE_ERRORS as exc:
                delay = self._retry.backoff(attempt, self._rand)
                if attempt >= self._retry.max_retries or not self._fits(waited, delay):
                    raise NetworkError("Could not reach {}: {}".format(url, exc)) from exc
                self._wait(delay, url, str(exc))
                waited += delay
                attempt += 1
                continue
            except requests.RequestException as exc:
                raise NetworkError("Request to {} failed: {}".format(url, exc)) from exc

            status = response.status_code
            if status == 200:
                return response.text
            if status == 404:
                raise NotFoundError("Not found: {}".format(url))
            if status not in RETRYABLE_STATUS:
                raise RtpPlayError("Unexpected HTTP {} for {}".format(status, url))

            retry_after = parse_retry_after(response.headers.get("Retry-After"), self._now)
            if retry_after is not None and retry_after > self._retry.max_retry_after:
                raise self._give_up(status, url, retry_after)
            if attempt >= self._retry.max_retries:
                raise self._give_up(status, url, retry_after)
            delay = self._retry.backoff(attempt, self._rand) if retry_after is None else retry_after
            if not self._fits(waited, delay):
                raise self._give_up(status, url, retry_after)
            self._wait(delay, url, "HTTP {}".format(status))
            waited += delay
            attempt += 1

    def exists(self, url: str) -> bool:
        """Whether ``url`` answers HTTP 200. Reads no body.

        One quick try without retries: callers have a fallback, and backing off
        from a failing server would only delay playback.
        """
        self._limiter.acquire()
        try:
            response = self._session.get(
                url, headers=DEFAULT_HEADERS, timeout=PROBE_TIMEOUT, stream=True
            )
        except requests.RequestException as exc:
            log.debug("Could not reach %s: %s", url, exc)
            return False
        response.close()
        return response.status_code == 200

    def _fits(self, waited: float, delay: float) -> bool:
        return waited + delay <= self._retry.max_total_wait

    def _wait(self, delay: float, url: str, reason: str) -> None:
        log.warning("Retrying %s in %.1fs (%s)", url, delay, reason)
        self._sleep(delay)

    @staticmethod
    def _give_up(status: int, url: str, retry_after: Optional[float]) -> RtpPlayError:
        if status == 429:
            return RateLimitedError("Rate limited by RTP Play ({})".format(url), retry_after)
        return NetworkError("RTP Play unavailable (HTTP {}) for {}".format(status, url))
