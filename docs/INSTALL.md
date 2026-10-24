# Installing on Kodi

Install from the add-on's Kodi repository, so Kodi installs the dependencies and keeps the add-on updated. The device needs internet access.

## 1. Allow unknown sources (first time only)

Kodi blocks zip installs by default.

1. *Settings* (gear icon) → *System* → *Add-ons*
2. Turn on **Unknown sources** and confirm the warning.

## 2. Add the repository source

1. *Settings* → *File manager* → **Add source**
2. Select *&lt;None&gt;*, enter `https://ricardopinheiro03.github.io/plugin.video.modernrtpplay/` and select *OK*.
3. Name the source `rtpplay` and select *OK*.

## 3. Install the repository

1. *Settings* → *Add-ons* → **Install from zip file** → `rtpplay`
2. Select `repository.modernrtpplay-<version>.zip` and wait for the "Add-on installed" notification.

## 4. Install RTP Play

1. *Settings* → *Add-ons* → **Install from repository** → *RTP Play Repository* → *Video add-ons* → **RTP Play**
2. Select *Install*. Kodi also installs `script.module.requests` and **InputStream Adaptive**, which the add-on needs for all playback.

The add-on then appears under *Add-ons* → *Video add-ons* → **RTP Play**.

### InputStream Adaptive on Linux

If your distribution packages Kodi itself (rather than Flatpak or the official builds), InputStream Adaptive may be missing from Kodi's repository, so step 4 fails with a dependency error. Install the system package (for example `sudo dnf install kodi-inputstream-adaptive` on Fedora with RPM Fusion), restart Kodi, enable it under *My add-ons* → *VideoPlayer InputStream*, and repeat step 4.

## Without the repository

Download `plugin.video.modernrtpplay-<version>.zip` from the [latest release](https://github.com/RicardoPinheiro03/plugin.video.modernrtpplay/releases/latest), or build it yourself (only Python 3 is needed):

```sh
git clone https://github.com/RicardoPinheiro03/plugin.video.modernrtpplay.git
cd plugin.video.modernrtpplay
python3 scripts/build_zip.py        # writes dist/plugin.video.modernrtpplay-<version>.zip
```

Then use *Install from zip file* and pick that zip. These installs are not updated automatically: install a newer zip the same way to upgrade.

## Updating

Installs from the repository update automatically. To update right away: *Add-ons* → *My add-ons* → **RTP Play** → *Update*.

## Uninstalling

*Add-ons* → *Video add-ons* → long-press or right-click **RTP Play** → *Information* → *Uninstall*. Uninstall *RTP Play Repository* the same way under *My add-ons* → *Add-on repository*.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| "RTP Play is limiting requests…" | RTP is throttling requests. Wait the number of seconds shown and try again. |
| "Could not load content from RTP Play" | Check internet access, then open the [Kodi log](https://kodi.wiki/view/Log_file) and look for lines starting with `[plugin.video.modernrtpplay]`. If a page fails to parse, RTP probably changed their site; please open an issue with that log excerpt. |
| Videos do not start | Check that InputStream Adaptive is installed and enabled (*My add-ons* → *VideoPlayer InputStream*). Some programs are geo-restricted to Portugal or not licensed for online streaming. |
| Old `plugin.video.rtpplay` still installed | They can coexist (different add-on ids), but the old one no longer works and can be uninstalled. |
