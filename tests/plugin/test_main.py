import os

from plugin.main import run

BASE = "plugin://plugin.video.modernrtpplay/"


def test_run_keeps_its_cache_in_the_profile_folder(kodi, tmp_path):
    kodi.profile = str(tmp_path / "addon_data")
    run([BASE, "1", ""])  # the root menu makes no requests
    assert os.path.isfile(os.path.join(kodi.profile, "cache.db"))
    assert kodi.end["succeeded"]


def test_run_works_without_a_usable_cache_file(kodi, tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("")
    kodi.profile = str(blocker)
    run([BASE, "1", ""])
    assert kodi.end["succeeded"]
