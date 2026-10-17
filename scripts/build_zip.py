"""Package the add-on as an installable Kodi zip.

Usage: python scripts/build_zip.py [--output DIR]

Writes DIR/<addon id>-<version>.zip containing a single top-level folder named
after the add-on id, which is the layout Kodi's "Install from zip file" expects.
Only runtime files are included (no tests, CI or docs).
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Paths (relative to the repository root) shipped in the zip.
INCLUDE = ("addon.xml", "main.py", "LICENSE", "icon.png", "fanart.jpg", "resources")
EXCLUDE_DIRS = {"__pycache__"}


def read_addon(root):
    addon = ET.parse(os.path.join(root, "addon.xml")).getroot()
    return addon.get("id"), addon.get("version")


def build(root, output):
    addon_id, version = read_addon(root)
    os.makedirs(output, exist_ok=True)
    path = os.path.join(output, "{}-{}.zip".format(addon_id, version))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in INCLUDE:
            source = os.path.join(root, name)
            if os.path.isfile(source):
                archive.write(source, os.path.join(addon_id, name))
            elif os.path.isdir(source):
                for folder, dirs, files in os.walk(source):
                    dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
                    for file_name in sorted(files):
                        if file_name.endswith(".pyc"):
                            continue
                        full = os.path.join(folder, file_name)
                        archive.write(full, os.path.join(addon_id, os.path.relpath(full, root)))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=os.path.join(ROOT, "dist"))
    args = parser.parse_args(argv)
    print(build(ROOT, args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
