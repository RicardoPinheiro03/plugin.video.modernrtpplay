# Installing on Kodi

The add-on is distributed as a zip file. Kodi installs it together with its dependencies.

## 1. Get the zip

Pick one:

- **From CI (any branch or pull request):** open the repository's *Actions* tab, choose a successful **CI** run, and download the `addon-zip` artifact. GitHub wraps it in another zip, so extract it once to get `plugin.video.modernrtpplay-<version>.zip`.
- **Build it yourself:**
  ```sh
  git clone https://github.com/RicardoPinheiro03/plugin.video.modernrtpplay.git
  cd plugin.video.modernrtpplay
  python3 scripts/build_zip.py        # writes dist/plugin.video.modernrtpplay-<version>.zip
  ```
  Building only needs Python 3; no packages are required.

Copy the zip somewhere Kodi can see it: local storage, a USB drive, or a network share.

## 2. Allow unknown sources (first time only)

Kodi blocks zip installs by default.

1. *Settings* (gear icon) → *System* → *Add-ons*
2. Turn on **Unknown sources** and confirm the warning.

## 3. Install from zip

1. *Settings* → *Add-ons* → **Install from zip file**
2. Browse to the zip and select it.
3. Wait for the "Add-on installed" notification. Kodi also installs `script.module.requests` from the official repository, so the device needs internet access.

The add-on then appears under *Add-ons* → *Video add-ons* → **RTP Play**, and also under music add-ons.

## 4. (Recommended) Install InputStream Adaptive

Live TV and most on-demand videos are HLS streams. Kodi can play them natively, but `inputstream.adaptive` handles them better (adaptive bitrate, fewer stalls).

*Settings* → *Add-ons* → *Install from repository* → *VideoPlayer InputStream* → **InputStream Adaptive** → *Install*.

On some Linux distributions it is a separate system package (for example `kodi-inputstream-adaptive`). The add-on detects it automatically, so nothing needs configuring.

## Updating

Install the newer zip the same way; Kodi upgrades in place. Zip installs are not updated automatically.

## Uninstalling

*Add-ons* → *Video add-ons* → long-press or right-click **RTP Play** → *Information* → *Uninstall*.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| "RTP Play is limiting requests…" | RTP is throttling requests. Wait the number of seconds shown and try again. |
| "Could not load content from RTP Play" | Check internet access, then open the [Kodi log](https://kodi.wiki/view/Log_file) and look for lines starting with `[plugin.video.modernrtpplay]`. If a page fails to parse, RTP probably changed their site; please open an issue with that log excerpt. |
| Live channel does not start | Install InputStream Adaptive (step 4). Some channels or events are geo-restricted to Portugal or not licensed for online streaming. |
| Old `plugin.video.rtpplay` still installed | They can coexist (different add-on ids), but the old one no longer works and can be uninstalled. |
