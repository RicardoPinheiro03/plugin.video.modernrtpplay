"""Fake ``xbmc*`` modules so the plugin layer runs outside Kodi.

Every call that matters is recorded on the ``kodi`` fixture.
"""

import os
import sys
import types

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

STRINGS = {
    30000: "Live",
    30001: "Programs",
    30002: "Search",
    30003: "Next page",
    30004: "Rate limited, retry in %d s",
    30005: "Rate limited",
    30006: "Load failed",
    30007: "Search RTP Play",
    30008: "Season %s",
    30009: "TV Shows",
    30010: "Movies",
}


class Recorder:
    def __init__(self):
        self.reset()

    def reset(self):
        self.items = []
        self.end = None
        self.content = None
        self.resolved = None
        self.notifications = []
        self.input_text = ""
        self.profile = ""


kodi_state = Recorder()


class InfoTag:
    def __init__(self):
        self.title = None
        self.plot = None
        self.media_type = None
        self.year = None
        self.duration = None

    def setTitle(self, title):
        self.title = title

    def setPlot(self, plot):
        self.plot = plot

    def setMediaType(self, media_type):
        self.media_type = media_type

    def setYear(self, year):
        self.year = year

    def setDuration(self, duration):
        self.duration = duration


class ListItem:
    def __init__(self, label="", path="", offscreen=False):
        self.label = label
        self.path = path
        self.art = {}
        self.properties = {}
        self.mime_type = None
        self.content_lookup = True
        self.video_tag = InfoTag()
        self.music_tag = InfoTag()

    def setArt(self, art):
        self.art.update(art)

    def setProperty(self, key, value):
        self.properties[key] = value

    def setMimeType(self, mime_type):
        self.mime_type = mime_type

    def setContentLookup(self, enabled):
        self.content_lookup = enabled

    def getVideoInfoTag(self):
        return self.video_tag

    def getMusicInfoTag(self):
        return self.music_tag


class Dialog:
    def input(self, heading):
        return kodi_state.input_text

    def notification(self, heading, message, icon=None, time=5000):
        kodi_state.notifications.append((heading, message))


class Addon:
    def getLocalizedString(self, string_id):
        return STRINGS[string_id]

    def getAddonInfo(self, key):
        info = {"name": "RTP Play", "id": "plugin.video.modernrtpplay"}
        info["profile"] = kodi_state.profile
        return info[key]


def _install_fakes():
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG, xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR = 0, 1, 2, 3
    xbmc.log = lambda message, level=0: None

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.ListItem = ListItem
    xbmcgui.Dialog = Dialog
    xbmcgui.NOTIFICATION_ERROR = "error"

    xbmcplugin = types.ModuleType("xbmcplugin")

    def add_items(handle, items, total=0):
        kodi_state.items.extend(items)

    def end(handle, succeeded=True, updateListing=False, cacheToDisc=True):
        kodi_state.end = {"succeeded": succeeded, "cache": cacheToDisc}

    def set_content(handle, content):
        kodi_state.content = content

    def resolve(handle, succeeded, item):
        kodi_state.resolved = (succeeded, item)

    xbmcplugin.addDirectoryItems = add_items
    xbmcplugin.endOfDirectory = end
    xbmcplugin.setContent = set_content
    xbmcplugin.setResolvedUrl = resolve

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = Addon

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = lambda path: path

    sys.modules.update(
        {
            "xbmc": xbmc,
            "xbmcgui": xbmcgui,
            "xbmcplugin": xbmcplugin,
            "xbmcaddon": xbmcaddon,
            "xbmcvfs": xbmcvfs,
        }
    )


_install_fakes()


@pytest.fixture
def kodi():
    kodi_state.reset()
    return kodi_state
