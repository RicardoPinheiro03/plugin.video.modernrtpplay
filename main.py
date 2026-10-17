"""Kodi entry point: Kodi runs this file once per navigation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

from plugin.main import run  # noqa: E402

run(sys.argv)
