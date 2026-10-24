"""Build the Kodi repository that GitHub Pages serves.

Usage: python scripts/build_repo.py [--output DIR] ADDON_ZIP...

Takes add-on zips built by build_zip.py, packages repository.modernrtpplay next to
them and writes the layout the repository's addon.xml points at:

    DIR/index.html                          link Kodi's file browser shows
    DIR/repository.modernrtpplay-<v>.zip    the zip users install once
    DIR/addons.xml, DIR/addons.xml.md5      what Kodi polls for updates
    DIR/<addon id>/<addon id>-<v>.zip       one folder per add-on (datadir)
"""

import argparse
import hashlib
import os
import shutil
import sys
import zipfile

import build_zip

ROOT = build_zip.ROOT
REPOSITORY = os.path.join(ROOT, "repository.modernrtpplay")

INDEX = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>RTP Play Repository</title></head>
<body>
<a href="{0}">{0}</a>
</body>
</html>
"""


def addon_xml(zip_path):
    """Return (addon id, addon.xml text) from a zip with one top-level add-on folder."""
    with zipfile.ZipFile(zip_path) as archive:
        name = next(n for n in archive.namelist() if n.count("/") == 1 and n.endswith("/addon.xml"))
        text = archive.read(name).decode("utf-8")
    return name.split("/")[0], text


def build(addon_zips, output, repository=REPOSITORY):
    os.makedirs(output, exist_ok=True)
    repository_zip = build_zip.build(repository, output)

    entries = []
    for path in [repository_zip, *addon_zips]:
        addon_id, text = addon_xml(path)
        folder = os.path.join(output, addon_id)
        os.makedirs(folder, exist_ok=True)
        shutil.copy(path, folder)
        # Drop the XML declaration: addons.xml wraps every entry in one document.
        entries.append(text.split("?>", 1)[-1].strip() if text.startswith("<?xml") else text)

    index = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n{}\n</addons>\n'
    content = index.format("\n".join(entries)).encode("utf-8")
    with open(os.path.join(output, "addons.xml"), "wb") as handle:
        handle.write(content)
    with open(os.path.join(output, "addons.xml.md5"), "w") as handle:
        handle.write(hashlib.md5(content).hexdigest())
    with open(os.path.join(output, "index.html"), "w") as handle:
        handle.write(INDEX.format(os.path.basename(repository_zip)))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=os.path.join(ROOT, "dist", "site"))
    parser.add_argument("addon_zips", nargs="+", metavar="ADDON_ZIP")
    args = parser.parse_args(argv)
    print(build(args.addon_zips, args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
