import hashlib
import os
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import build_repo  # noqa: E402
import build_zip  # noqa: E402

ADDON_XML = '<?xml version="1.0"?><addon id="{}" version="{}"></addon>'


def make_addon(root, addon_id, version):
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "addon.xml"), "w") as handle:
        handle.write(ADDON_XML.format(addon_id, version))
    return root


def test_build_writes_the_layout_kodi_expects(tmp_path):
    plugin_zip = build_zip.build(
        make_addon(str(tmp_path / "plugin"), "plugin.video.test", "1.2.3"), str(tmp_path / "dist")
    )
    repository = make_addon(str(tmp_path / "repo"), "repository.test", "1.0.0")
    site = str(tmp_path / "site")

    build_repo.build([plugin_zip], site, repository)

    files = sorted(
        os.path.relpath(os.path.join(d, f), site) for d, _, fs in os.walk(site) for f in fs
    )
    assert files == [
        "addons.xml",
        "addons.xml.md5",
        "index.html",
        "plugin.video.test/plugin.video.test-1.2.3.zip",
        "repository.test-1.0.0.zip",
        "repository.test/repository.test-1.0.0.zip",
    ]
    with open(os.path.join(site, "addons.xml"), "rb") as handle:
        content = handle.read()
    addons = ET.fromstring(content)
    assert [(a.get("id"), a.get("version")) for a in addons] == [
        ("repository.test", "1.0.0"),
        ("plugin.video.test", "1.2.3"),
    ]
    with open(os.path.join(site, "addons.xml.md5")) as handle:
        assert handle.read() == hashlib.md5(content).hexdigest()
    with open(os.path.join(site, "index.html")) as handle:
        assert '<a href="repository.test-1.0.0.zip">' in handle.read()


def test_main_prints_the_site_path(tmp_path, capsys):
    plugin_zip = build_zip.build(
        make_addon(str(tmp_path / "plugin"), "plugin.video.test", "1.2.3"), str(tmp_path / "dist")
    )

    assert build_repo.main(["--output", str(tmp_path / "site"), plugin_zip]) == 0

    assert capsys.readouterr().out.strip() == str(tmp_path / "site")


REPOSITORY_XML = """<?xml version="1.0"?>
<addon id="repository.test" version="1.0.0">
  <extension point="xbmc.addon.repository">
    <dir>
      <info>https://example.org/repo/addons.xml</info>
      <checksum>https://example.org/repo/addons.xml.md5</checksum>
      <datadir zip="true">https://example.org/repo/</datadir>
    </dir>
  </extension>
  <extension point="xbmc.addon.metadata"><source>https://github.com/o/r</source></extension>
</addon>
"""


def make_site(tmp_path, repository_xml=REPOSITORY_XML, releases=()):
    plugin_zip = build_zip.build(
        make_addon(str(tmp_path / "plugin"), "plugin.video.test", "1.2.3"), str(tmp_path / "dist")
    )
    repository = str(tmp_path / "repo")
    os.makedirs(repository)
    with open(os.path.join(repository, "addon.xml"), "w") as handle:
        handle.write(repository_xml)
    return build_repo.build([plugin_zip], str(tmp_path / "site"), repository, releases)


def read(path):
    with open(path) as handle:
        return handle.read()


def test_index_lists_releases_and_the_install_source(tmp_path):
    site = make_site(
        tmp_path, releases=[{"tagName": "v1.2.3", "publishedAt": "2026-10-24T12:00:00Z"}]
    )

    index = read(os.path.join(site, "index.html"))
    assert "<code>https://example.org/repo/</code>" in index
    assert '<a href="https://github.com/o/r/releases/tag/v1.2.3">Release notes</a>' in index
    assert "https://github.com/o/r/releases/download/v1.2.3/plugin.video.test-1.2.3.zip" in index
    assert "2026-10-24" in index
    build_repo.check(site)


def test_index_without_releases(tmp_path):
    assert "No releases yet." in read(os.path.join(make_site(tmp_path), "index.html"))


def test_check_rejects_a_stale_checksum(tmp_path):
    site = make_site(tmp_path)
    with open(os.path.join(site, "addons.xml.md5"), "w") as handle:
        handle.write("0" * 32)
    with pytest.raises(ValueError, match="md5"):
        build_repo.check(site)


def test_check_rejects_a_missing_zip(tmp_path):
    site = make_site(tmp_path)
    os.remove(os.path.join(site, "plugin.video.test", "plugin.video.test-1.2.3.zip"))
    with pytest.raises(ValueError, match="missing"):
        build_repo.check(site)


def test_check_rejects_urls_outside_the_datadir(tmp_path):
    site = make_site(tmp_path, REPOSITORY_XML.replace("repo/addons.xml<", "old/addons.xml<"))
    with pytest.raises(ValueError, match="<info>"):
        build_repo.check(site)


def test_check_requires_the_index_to_link_the_repository_zip(tmp_path):
    site = make_site(tmp_path)
    with open(os.path.join(site, "index.html"), "w") as handle:
        handle.write("<html></html>")
    with pytest.raises(ValueError, match="index.html"):
        build_repo.check(site)


def test_main_reads_releases(tmp_path, capsys):
    plugin_zip = build_zip.build(
        make_addon(str(tmp_path / "plugin"), "plugin.video.test", "1.2.3"), str(tmp_path / "dist")
    )
    releases = tmp_path / "releases.json"
    releases.write_text('[{"tagName": "v1.2.3", "publishedAt": "2026-10-24T12:00:00Z"}]')

    assert (
        build_repo.main(["--output", str(tmp_path / "s"), "--releases", str(releases), plugin_zip])
        == 0
    )

    assert "releases/tag/v1.2.3" in read(str(tmp_path / "s" / "index.html"))
