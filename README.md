# plugin.video.modernrtpplay

Watch [RTP Play](https://www.rtp.pt/play) on-demand programs in Kodi. It replaces [plugin.video.rtpplay](https://github.com/enen92/plugin.video.rtpplay), which no longer works.

> Unofficial and not endorsed by RTP. Changes to RTP's website can break it until the add-on is updated.

## Install

1. *Settings* → *System* → *Add-ons* → turn on **Unknown sources**.
2. *Settings* → *File manager* → *Add source* → enter `https://ricardopinheiro03.github.io/plugin.video.modernrtpplay/` and name it `rtpplay`.
3. *Settings* → *Add-ons* → *Install from zip file* → `rtpplay` → `repository.modernrtpplay-<version>.zip`.
4. *Install from repository* → *RTP Play Repository* → *Video add-ons* → **RTP Play** → *Install*.

Kodi keeps the add-on updated from then on. Other ways to install are in [docs/INSTALL.md](docs/INSTALL.md).

## Features

- Browse TV shows by season and movies, with synopses, posters and fan art
- Browse every on-demand program by category (news, fiction, sports, kids and more)
- Shows with several seasons list their seasons first, then the episodes
- Search the RTP Play catalogue

Live TV and radio are not available yet.

## Requirements

- Kodi 20 (Nexus) or newer
- **InputStream Adaptive**, which is required for all playback. Kodi installs it with the add-on. If your Linux distribution packages Kodi itself, install the system package instead (for example `kodi-inputstream-adaptive`).

## More

[Installing](docs/INSTALL.md) · [Developer guide](docs/DEVELOPING.md) · [Changelog](CHANGELOG.md) · License: [GPL-3.0-only](LICENSE)
