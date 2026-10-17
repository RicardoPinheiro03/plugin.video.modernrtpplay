"""Wires Kodi's invocation to the RTP Play client."""

from __future__ import annotations

import logging
from typing import List

import xbmc

from rtpplay import RtpPlayClient

from .routing import parse_argv
from .views import Addon

_LEVELS = {
    logging.DEBUG: xbmc.LOGDEBUG,
    logging.INFO: xbmc.LOGINFO,
    logging.WARNING: xbmc.LOGWARNING,
    logging.ERROR: xbmc.LOGERROR,
}


class KodiLogHandler(logging.Handler):
    """Sends Python ``logging`` records to kodi.log."""

    def emit(self, record: logging.LogRecord) -> None:
        level = _LEVELS.get(record.levelno, xbmc.LOGERROR)
        xbmc.log("[plugin.video.modernrtpplay] " + self.format(record), level)


def run(argv: List[str]) -> None:
    root = logging.getLogger()
    if not any(isinstance(h, KodiLogHandler) for h in root.handlers):
        root.addHandler(KodiLogHandler())
        root.setLevel(logging.DEBUG)
    Addon(RtpPlayClient(), parse_argv(argv)).dispatch()
