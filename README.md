# plugin.video.modernrtpplay

A Kodi add-on for [RTP Play](https://www.rtp.pt/play): on-demand RTP programs you can browse by category or search.

It replaces [plugin.video.rtpplay](https://github.com/enen92/plugin.video.rtpplay), which stopped working ("could not retrieve TV shows") because RTP's mobile-app API now rejects third-party clients. This add-on reads the public RTP Play website instead.

> Unofficial and not endorsed by RTP. If RTP changes their website, parts of the add-on can break until the parsers are updated.

## Features

- **Programs**: all programs per category (A–Z), with paginated episode lists
- **Search** across the RTP Play catalogue
- Plays HLS, DASH and direct audio/video; uses `inputstream.adaptive` when installed
- Polite to RTP's servers: it caps its own request rate and backs off when the site returns HTTP 429 or 5xx (see [rate limiting](docs/DEVELOPING.md#rate-limiting))

## Requirements

- Kodi 20 (Nexus) or newer
- `script.module.requests` (installed automatically from the official Kodi repository)
- Optional: `inputstream.adaptive`, recommended for HLS/DASH streams

## Documentation

- [Installing on Kodi](docs/INSTALL.md)
- [Developer guide: architecture, adding features, testing, releasing](docs/DEVELOPING.md)
- [Future tasks](docs/FUTURE.md)
- [Changelog](CHANGELOG.md)

## License

GPL-3.0-only. See [LICENSE](LICENSE).
