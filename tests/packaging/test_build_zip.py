import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import build_zip  # noqa: E402

ADDON_XML = '<?xml version="1.0"?><addon id="plugin.video.test" version="1.2.3"></addon>'


def write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(content)


def test_build_packages_runtime_files_under_the_addon_folder(tmp_path):
    root = str(tmp_path / "repo")
    write(os.path.join(root, "addon.xml"), ADDON_XML)
    write(os.path.join(root, "main.py"))
    write(os.path.join(root, "resources", "lib", "rtpplay", "client.py"))
    write(os.path.join(root, "resources", "lib", "rtpplay", "__pycache__", "client.cpython.pyc"))
    write(os.path.join(root, "tests", "test_x.py"))
    write(os.path.join(root, ".github", "workflows", "ci.yml"))

    path = build_zip.build(root, str(tmp_path / "dist"))

    assert os.path.basename(path) == "plugin.video.test-1.2.3.zip"
    with zipfile.ZipFile(path) as archive:
        assert sorted(archive.namelist()) == [
            "plugin.video.test/addon.xml",
            "plugin.video.test/main.py",
            "plugin.video.test/resources/lib/rtpplay/client.py",
        ]
