"""Exceptions raised by the RTP Play client.

Every error derives from :class:`RtpPlayError`, so callers can catch one type
and still branch on the specific failure when they need to.
"""

from __future__ import annotations

from typing import Optional


class RtpPlayError(Exception):
    """Base class for every error raised by this package."""


class NetworkError(RtpPlayError):
    """The server could not be reached, or kept failing after all retries."""


class NotFoundError(RtpPlayError):
    """The requested page does not exist (HTTP 404)."""


class RateLimitedError(RtpPlayError):
    """RTP Play is throttling us (HTTP 429) and retrying did not help.

    ``retry_after`` is the number of seconds the server asked us to wait, when
    it told us; ``None`` otherwise.
    """

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ParseError(RtpPlayError):
    """A page was fetched but did not have the structure we expect.

    This usually means RTP changed their website and a parser needs updating.
    """
