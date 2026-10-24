"""Build the Kodi repository that GitHub Pages serves.

Usage: python scripts/build_repo.py [--output DIR] [--releases JSON] ADDON_ZIP...

Takes add-on zips built by build_zip.py, packages repository.modernrtpplay next to
them and writes the layout the repository's addon.xml points at:

    DIR/index.html                          release index; Kodi's file browser shows its zip link
    DIR/repository.modernrtpplay-<v>.zip    the zip users install once
    DIR/addons.xml, DIR/addons.xml.md5      what Kodi polls for updates
    DIR/<addon id>/<addon id>-<v>.zip       one folder per add-on (datadir)

--releases takes `gh release list --json tagName,publishedAt` output, newest first,
and lists those releases on the index page. The site is checked after it is built.
"""

import argparse
import hashlib
import html
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

import build_zip

ROOT = build_zip.ROOT
REPOSITORY = os.path.join(ROOT, "repository.modernrtpplay")

# Kodi's file browser lists only links whose text is their own href, so the repository
# zip link must stay that way, and every other link must have different text.
INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RTP Play Repository</title>
<style>
:root {{ --bg: #fff; --fg: #1d1d1f; --muted: #6e6e73; --line: #d2d2d7; --accent: #0a66c2; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #161617; --fg: #f5f5f7; --muted: #a1a1a6; --line: #3a3a3c; --accent: #4da3ff; }}
}}
body {{ margin: 0 auto; max-width: 44rem; padding: 2rem 1rem; background: var(--bg);
  color: var(--fg); font: 16px/1.5 system-ui, sans-serif; }}
a {{ color: var(--accent); }}
code {{ word-break: break-all; }}
.muted {{ color: var(--muted); }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: .5rem .25rem; border-bottom: 1px solid var(--line); text-align: left; }}
</style>
</head>
<body>
<h1>RTP Play Repository</h1>
<p>Kodi repository for <a href="{source}">plugin.video.modernrtpplay</a>.</p>
<h2>Install</h2>
<ol>
<li>In Kodi, add this page's address as a source: <code>{url}</code></li>
<li><em>Install from zip file</em> &rarr; that source &rarr;
<a href="{repository_zip}">{repository_zip}</a></li>
<li><em>Install from repository</em> &rarr; <em>RTP Play Repository</em> &rarr;
<em>RTP Play</em></li>
</ol>
<h2>Releases</h2>
{releases}
</body>
</html>
"""
RELEASE_ROW = (
    '<tr><td>{tag}</td><td class="muted">{date}</td>'
    '<td><a href="{source}/releases/tag/{tag}">Release notes</a></td>'
    '<td><a href="{source}/releases/download/{tag}/{zip}">Download zip</a></td></tr>'
)


def addon_xml(zip_path):
    """Return (addon id, addon.xml text) from a zip with one top-level add-on folder."""
    with zipfile.ZipFile(zip_path) as archive:
        name = next(n for n in archive.namelist() if n.count("/") == 1 and n.endswith("/addon.xml"))
        text = archive.read(name).decode("utf-8")
    return name.split("/")[0], text


def release_table(releases, source, addon_id):
    if not releases:
        return '<p class="muted">No releases yet.</p>'
    rows = []
    for release in releases:
        tag = release["tagName"]
        zip_name = "{}-{}.zip".format(addon_id, tag.lstrip("v"))
        values = {"tag": tag, "date": release["publishedAt"][:10], "zip": zip_name}
        values = {key: html.escape(value) for key, value in values.items()}
        rows.append(RELEASE_ROW.format(source=source, **values))
    return "<table>\n{}\n</table>".format("\n".join(rows))


def build(addon_zips, output, repository=REPOSITORY, releases=()):
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
    plugin_id = addon_xml(addon_zips[0])[0]
    repo = ET.parse(os.path.join(repository, "addon.xml")).getroot()
    source = html.escape(repo.findtext(".//source", ""))
    page = INDEX.format(
        url=html.escape(repo.findtext(".//datadir", "")),
        source=source,
        repository_zip=html.escape(os.path.basename(repository_zip)),
        releases=release_table(releases, source, plugin_id),
    )
    with open(os.path.join(output, "index.html"), "w") as handle:
        handle.write(page)
    return output


def check(output):
    """Raise ValueError unless the site is what Kodi will read from GitHub Pages."""
    with open(os.path.join(output, "addons.xml"), "rb") as handle:
        content = handle.read()
    with open(os.path.join(output, "addons.xml.md5")) as handle:
        if handle.read() != hashlib.md5(content).hexdigest():
            raise ValueError("addons.xml.md5 does not match addons.xml")
    with open(os.path.join(output, "index.html")) as handle:
        index = handle.read()
    for addon in ET.fromstring(content):
        addon_id, version = addon.get("id", ""), addon.get("version", "")
        zip_name = "{}-{}.zip".format(addon_id, version)
        if not os.path.isfile(os.path.join(output, addon_id, zip_name)):
            raise ValueError("{} is listed in addons.xml but missing".format(zip_name))
        datadir = addon.find(".//datadir")
        if datadir is None:
            continue
        base = datadir.text or ""
        expected = {"info": base + "addons.xml", "checksum": base + "addons.xml.md5"}
        for tag, url in expected.items():
            if addon.findtext(".//" + tag) != url:
                raise ValueError("{} <{}> is not {}".format(addon_id, tag, url))
        link = '<a href="{0}">{0}</a>'.format(zip_name)
        if link not in index or not os.path.isfile(os.path.join(output, zip_name)):
            raise ValueError("index.html does not link {}".format(zip_name))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=os.path.join(ROOT, "dist", "site"))
    parser.add_argument("--releases", help="JSON from gh release list, newest first")
    parser.add_argument("addon_zips", nargs="+", metavar="ADDON_ZIP")
    args = parser.parse_args(argv)
    releases = []
    if args.releases:
        with open(args.releases) as handle:
            releases = json.load(handle)
    output = build(args.addon_zips, args.output, releases=releases)
    check(output)
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
