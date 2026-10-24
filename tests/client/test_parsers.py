import pytest

from conftest import load_fixture
from rtpplay import parsers
from rtpplay.errors import ParseError
from rtpplay.models import DASH, HLS, PROGRESSIVE, RADIO, TV, EpisodeInfo, Season


def test_parse_programs():
    programs = parsers.parse_programs(load_fixture("programs.html"))
    assert [(p.id, p.title) for p in programs] == [
        (17251, "15:17 Destino Paris"),
        (13632, "2 Duros de Roer"),
    ]
    assert programs[0].thumbnail.startswith("https://cdn-images.rtp.pt/")


def test_parse_episodes():
    episodes = parsers.parse_episodes(load_fixture("episodes.html"))
    first = episodes[0]
    assert len(episodes) == 2
    assert (first.program_id, first.id) == (1525, 892592)
    assert first.title == "A Mosca - Pausa"
    assert first.path == "/play/p1525/e892592/a-mosca"
    assert first.date == "28 nov. 2025"


def test_parse_numbered_episodes_label_with_the_episode_number():
    # Series cards often carry only the program name in their link title.
    episodes = parsers.parse_episodes(load_fixture("episodes_numbered.html"))
    assert [e.title for e in episodes] == ["Ep. 1 - A Revolução", "Ep. 1"]
    assert episodes[1].path == "/play/p17168/e955155/a-familia-hardacre"


def test_parse_seasons_from_the_program_page_selector():
    seasons = parsers.parse_seasons(load_fixture("program_seasons.html"))
    assert seasons == [
        Season(10209, "Temporada 2", 2),
        Season(5057, "Temporada 1", 1),
    ]


def test_parse_seasons_of_a_single_season_program():
    assert parsers.parse_seasons(load_fixture("program.html")) == []


def test_parse_seasons_keeps_titles_that_are_not_plain_season_numbers():
    page = (
        '<div class="container seasons-container"><select>'
        '<option value="/play/p1/x">Especial 25 Anos</option>'
        '<option value="/play/p2/x">Temporada 2023/2024</option></select></div>'
        '<select><option value="/play/p3/related">Other program</option></select>'
    )
    assert parsers.parse_seasons(page) == [
        Season(1, "Especial 25 Anos", None),
        Season(2, "Temporada 2023/2024", None),
    ]


def test_parse_search_results_join_program_and_episode_lead():
    episodes = parsers.parse_episodes(load_fixture("search.html"))
    assert episodes[0].title == "Telejornal Açores - Telejornal, 10 de agosto"
    assert episodes[0].path == "/play/p56/e422725/telejornal-acores"


def test_parse_lists_ignore_empty_fragments():
    assert parsers.parse_programs("") == []
    assert parsers.parse_episodes("<!-- no more -->") == []


def test_parse_live_channels():
    channels = parsers.parse_live_channels(load_fixture("live.html"))
    assert [(c.slug, c.name, c.kind) for c in channels] == [
        ("rtp1", "RTP1", TV),
        ("antena1", "RTP Antena 1", RADIO),
    ]
    assert channels[0].now_playing == "Estrelas ao Sábado"
    assert channels[0].thumbnail.startswith("https://")


def test_parse_live_channels_fails_loudly_when_markup_changes():
    with pytest.raises(ParseError):
        parsers.parse_live_channels("<html></html>")


def test_parse_live_stream():
    stream = parsers.parse_live_stream(load_fixture("live_channel.html"))
    assert stream.url.startswith("https://streaming-live.rtp.pt/liverepeater/smil:rtp1HD.smil/")
    assert "tk=" in stream.url
    assert stream.protocol == HLS
    assert stream.is_live


def test_parse_episode_stream_uses_last_player_and_deobfuscates():
    stream = parsers.parse_episode_stream(load_fixture("episode_tv.html"))
    assert stream.url == (
        "https://streaming-vod.rtp.pt/hls/nas2.share,/h264/512x384/p1525/"
        "p1525_1_2025112820842.mp4,.urlset/master.m3u8"
    )
    assert stream.protocol == HLS
    assert not stream.is_live


def test_parse_episode_stream_prefers_hls_on_drm_flagged_pages():
    # Fiction pages name the HLS URL "fps" (FairPlay); it used to fall through to DASH.
    stream = parsers.parse_episode_stream(load_fixture("episode_fiction.html"))
    assert stream.url == (
        "https://streaming-vod.rtp.pt/hls/nas2.share,"
        "/pt/h264/512x384/p10209/p10209_1_20240501143408e001t7005d_lo.mp4,"
        "/pt/h264/512x384/p10209/p10209_1_20240501143408e001t7005d.mp4,.urlset/master.m3u8"
    )
    assert stream.protocol == HLS


def test_parse_episode_stream_progressive_audio():
    stream = parsers.parse_episode_stream(load_fixture("episode_radio.html"))
    assert stream.url.endswith(".mp3")
    assert stream.protocol == PROGRESSIVE


def test_parse_episode_stream_rewrites_drm_paths_to_clear_ones():
    page = 'var f = {hls : "https://streaming-vod.rtp.pt/drm-fps/a/master.m3u8"};'
    assert (
        parsers.parse_episode_stream(page).url == "https://streaming-vod.rtp.pt/hls/a/master.m3u8"
    )


def test_parse_episode_stream_falls_back_to_dash():
    page = 'var f = {hls : "", dash : "https://streaming-vod.rtp.pt/drm-dash/a/manifest.mpd"};'
    stream = parsers.parse_episode_stream(page)
    assert stream.url == "https://streaming-vod.rtp.pt/dash/a/manifest.mpd"
    assert stream.protocol == DASH


def test_parse_episode_stream_skips_dead_legacy_host():
    page = 'var f = {hls : "https://streaming-ondemand.rtp.pt/x/masters.m3u8"};'
    with pytest.raises(ParseError):
        parsers.parse_episode_stream(page)


def test_parse_episode_stream_without_player():
    with pytest.raises(ParseError):
        parsers.parse_episode_stream("<html></html>")


@pytest.mark.parametrize("parts", ['["%ZZ"]', '["/w=="]', "[1]"])
def test_parse_episode_stream_reports_broken_obfuscation_as_parse_error(parts):
    page = 'var f = {hls : atob(decodeURIComponent(%s.join("")))};' % parts
    with pytest.raises(ParseError):
        parsers.parse_episode_stream(page)


VOD = "https://streaming-vod.rtp.pt"
FILES = "/pt/h264/512x384/p13643/p13643_1_20261019161102e001t3729d"


@pytest.mark.parametrize("protocol, manifest", [("hls", "master.m3u8"), ("dash", "manifest.mpd")])
def test_with_hi_rendition_adds_the_1080p_file_last(protocol, manifest):
    files = "{}/{}/nas2.share,{f}_lo.mp4,{f}.mp4".format(VOD, protocol, f=FILES)
    url = files + ",.urlset/" + manifest
    assert parsers.with_hi_rendition(url) == files + ",{}_hi.mp4,.urlset/{}".format(FILES, manifest)


@pytest.mark.parametrize(
    "url",
    [
        VOD + "/hls/nas2.share,{f}_lo.mp4,{f}.mp4,{f}_hi.mp4,.urlset/master.m3u8".format(f=FILES),
        VOD + "/hls/nas2.share,/h264/512x384/p10431/p10431_20220622002904et7682.mp4"
        ",.urlset/master.m3u8",
        "https://cdn-ondemand.rtp.pt/nas2.share/wavrss/at1/2610/DLT3903125_606455.mp3",
        VOD + "/hls/nas2.share{}_lo.mp4/master.m3u8".format(FILES),
    ],
    ids=["already-has-hi", "single-file-urlset", "mp3", "not-a-urlset"],
)
def test_with_hi_rendition_leaves_other_urls_alone(url):
    assert parsers.with_hi_rendition(url) is None


def test_parse_collection():
    programs = parsers.parse_collection(load_fixture("collection.html"))
    assert [(p.id, p.title) for p in programs] == [
        (17336, "Lúcia e o Sexo"),
        (17297, "Sobretudo de Noite"),
        (17296, "Beleza Colateral"),
    ]
    assert programs[0].thumbnail.startswith("https://cdn-images.rtp.pt/EPG/imagens/")


def test_parse_collection_fails_loudly_when_markup_changes():
    with pytest.raises(ParseError):
        parsers.parse_collection("<html></html>")


def test_parse_program_info_of_a_film():
    info = parsers.parse_program_info(load_fixture("program_movie.html"), 17296)
    assert info.plot.startswith("Howard Inlet é um publicitário brilhante.")
    assert "recuperar.\nHoward começa" in info.plot  # <br /> becomes a line break
    assert info.year == 2016
    assert info.image.startswith("https://cdn-images.rtp.pt/EPG/imagens/a20/49533_80466_22406.jpg")
    assert info.episode_path == "/play/p17296/e961379/collateral-beauty"
    assert info.seasons == []


def test_parse_program_info_falls_back_to_the_json_ld_synopsis():
    page = load_fixture("program_movie.html").replace('<h2 class="lead">', "<h2>")
    info = parsers.parse_program_info(page, 17296)
    assert info.plot.startswith("Um filme de David Frankel, com Will Smith")
    assert "Peña" in info.plot  # HTML entities are decoded


def test_parse_program_info_ignores_episodes_of_other_programs():
    info = parsers.parse_program_info(load_fixture("program_movie.html"), 1)
    assert info.episode_path is None


def test_parse_program_info_of_a_page_without_details():
    info = parsers.parse_program_info(load_fixture("program_seasons.html"), 10209)
    assert (info.plot, info.year) == (None, None)
    assert [s.program_id for s in info.seasons] == [10209, 5057]


def test_parse_episode_info():
    info = parsers.parse_episode_info(load_fixture("episode_info.html"))
    assert info.plot.startswith("1941. Cândido de Oliveira")
    assert info.duration == 45 * 60 + 6
    assert info.image == "https://cdn-images.rtp.pt/EPG/imagens/a11/49435_80264_960.png?v=3&w=1170"


@pytest.mark.parametrize(
    "page",
    [
        "<html></html>",
        '<script type="application/ld+json">not json</script>',
        '<script type="application/ld+json">["a list"]</script>',
        '<script type="application/ld+json">{"duration": "soon"}</script>',
    ],
)
def test_parse_episode_info_without_details(page):
    assert parsers.parse_episode_info(page) == EpisodeInfo()
