# Changelog

All notable changes to this add-on are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- *TV Shows* and *Movies* in the main menu, built from RTP Play's series and film collections. Films play straight from the list; shows open their seasons. Both show their synopsis, year, poster and fan art.
- Episode lists show each episode's synopsis and duration.
- A cache in the add-on's profile folder (`cache.db`), so revisiting a list costs no requests: collections for 6 hours, program details for a day, episode details for 30 days.

## [0.2.0] - 2026-10-24

### Added

- Kodi repository (`repository.modernrtpplay`) on GitHub Pages: add one source URL in Kodi, install once, and the add-on updates automatically.
- Release workflow: pushing a `vX.Y.Z` tag runs CI, creates a GitHub release with the zips and publishes the repository.

### Changed

- InputStream Adaptive is now a required dependency, and HLS/DASH always play through it. Kodi installs it with the add-on.
- Opening a show lists its seasons first, then the episodes of the chosen season. Shows with a single season still open straight to their episodes. Series episodes are labelled with their number and title (e.g. "Ep. 1 - A Revolução").

### Removed

- *Live TV & Radio* from the main menu, until it's reworked (see `docs/FUTURE.md`). The client code for live channels is kept.

### Fixed

- Episodes of fiction and other DRM-flagged shows now play: their pages name the HLS stream `fps`, which was ignored, so playback fell back to DASH.

## [0.1.0] - 2026-10-17

### Added

- RTP Play client built on the public website (`rtpplay` package), replacing the retired mobile API used by `plugin.video.rtpplay`.
- Client-side rate limiting (token bucket) and retries with exponential backoff that honour `Retry-After` on HTTP 429/5xx.
- Kodi add-on: live TV and radio, programs by category, episode lists, search, and HLS/DASH/progressive playback (uses InputStream Adaptive when installed).
- English and Portuguese (pt_PT) translations.
- CI: lint, tests, zip build and `kodi-addon-checker` validation.
- Documentation: installation guide and developer guide.

[Unreleased]: https://github.com/RicardoPinheiro03/plugin.video.modernrtpplay/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/RicardoPinheiro03/plugin.video.modernrtpplay/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/RicardoPinheiro03/plugin.video.modernrtpplay/releases/tag/v0.1.0
