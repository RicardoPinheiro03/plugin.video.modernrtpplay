"""Client for the RTP Play website (www.rtp.pt/play).

This package has no Kodi dependencies, so it can be used and tested on its own::

    from rtpplay import RtpPlayClient

    client = RtpPlayClient()
    for channel in client.live_channels():
        print(channel.name)
"""

from .client import RtpPlayClient
from .errors import NetworkError, NotFoundError, ParseError, RateLimitedError, RtpPlayError
from .http import HttpClient, RateLimiter, RetryPolicy
from .models import Category, Channel, Episode, Page, Program, Stream

__all__ = [
    "Category",
    "Channel",
    "Episode",
    "HttpClient",
    "NetworkError",
    "NotFoundError",
    "Page",
    "ParseError",
    "Program",
    "RateLimitedError",
    "RateLimiter",
    "RetryPolicy",
    "RtpPlayClient",
    "RtpPlayError",
    "Stream",
]
