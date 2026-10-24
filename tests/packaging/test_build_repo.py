import hashlib
import os
import sys
import xml.etree.ElementTree as ET

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
