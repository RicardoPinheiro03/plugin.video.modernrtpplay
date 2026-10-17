# Future tasks

## Live TV & Radio

The main menu no longer shows *Live TV & Radio*, so the add-on never fetches `/play/direto`. The code for it is still there, so bringing it back means fixing and re-enabling it, not writing it from scratch:

- Client: `RtpPlayClient.live_channels()` and `live_stream()` in `resources/lib/rtpplay/client.py`, with their parsers and tests.
- Kodi: the `live` and `play_live` actions in `resources/lib/plugin/views.py`, and the string `#30000` ("Live TV & Radio").

To re-enable it, add the `live` folder back to `Addon.root()`, restore the `LIVE` string id, and test every channel in Kodi (TV over HLS, radio, and channels that are geo-restricted to Portugal).
