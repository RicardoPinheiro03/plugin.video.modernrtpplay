# Changelog

All notable changes to this add-on are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-17

### Added

- RTP Play client built on the public website (`rtpplay` package), replacing the retired mobile API used by `plugin.video.rtpplay`.
- Client-side rate limiting (token bucket) and retries with exponential backoff that honour `Retry-After` on HTTP 429/5xx.
- Kodi add-on: live TV and radio, programs by category, episode lists, search, and HLS/DASH/progressive playback (uses InputStream Adaptive when installed).
- English and Portuguese (pt_PT) translations.
- CI: lint, tests, zip build and `kodi-addon-checker` validation.
- Documentation: installation guide and developer guide.

[Unreleased]: https://github.com/RicardoPinheiro03/plugin.video.modernrtpplay/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RicardoPinheiro03/plugin.video.modernrtpplay/releases/tag/v0.1.0
