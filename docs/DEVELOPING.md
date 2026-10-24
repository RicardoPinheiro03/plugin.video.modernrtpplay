# Developer guide

## How it works

RTP has no public API. The mobile-app API used by the old `plugin.video.rtpplay` now answers every third-party request with `Request not authorized`, so this add-on reads the same pages a browser does:

| Data | Source on www.rtp.pt |
| --- | --- |
| Live channels | `/play/direto` (channel cards) |
| Live stream | `/play/direto/<slug>` (`hls_url = "..."` in the page script, carries a short-lived token) |
| Programs in a category | `/play/bg_l_pg/?listcategory=<id>&listtype=az&page=<n>` (HTML fragment) |
| Seasons of a program | `/play/p<id>/` (program page): the season `<select>`, whose options link to `/play/p<season id>/<slug>`. Each season is a program of its own; single-season programs have no selector |
| Episodes of a program | `/play/bg_l_ep/?listProgram=<id>&page=<n>` (HTML fragment) |
| Search | `/play/bg_l_s/?listQuery=<q>&page=<n>` (HTML fragment) |
| Episode stream | Episode page: the **last** `var f = {...}` / `file: {...}` player config, with URLs often obfuscated as `atob(decodeURIComponent([...].join("")))`. The HLS URL is keyed `hls`, or `fps` on DRM-flagged pages |

The streaming CDN only serves media to requests that carry a browser `User-Agent`, `Referer` and `Origin`. The client attaches these to every `Stream` it returns.

## Architecture

```
main.py                     Kodi entry point (one process per navigation)
repository.modernrtpplay/   Kodi repository add-on: points Kodi at the GitHub Pages site
scripts/                    build_zip.py (add-on zip), build_repo.py (Pages site)
resources/lib/
├── rtpplay/                Website client. Pure Python, no Kodi imports.
│   ├── client.py           RtpPlayClient: the only API the UI uses
│   ├── http.py             HttpClient: rate limiter, retries, browser headers
│   ├── parsers.py          HTML → models. The only code that knows the markup.
│   ├── models.py           Frozen dataclasses: Category, Channel, Program, Episode, Stream, Page
│   └── errors.py           RtpPlayError and subclasses
└── plugin/                 Kodi UI layer
    ├── main.py             run(argv): logging → kodi.log, builds client, dispatches
    ├── routing.py          plugin:// URL parsing and building (?action=...&...)
    └── views.py            Addon: one method per action, listings and playback
tests/
├── client/                 Parser tests on real-page fixtures, client and rate-limit tests
├── plugin/                 View tests with fake xbmc* modules and a fake client
└── packaging/              Zip and repository build tests
```

Design rules:

- **Dependencies point one way:** `plugin` → `rtpplay` → `requests`. The client never imports Kodi, so it can be tested and reused anywhere.
- **One public surface:** the UI talks to `RtpPlayClient` and gets typed, immutable models. It never sees HTML or HTTP.
- **Fail loudly, inside the domain:** everything raised is an `RtpPlayError` subclass (`NetworkError`, `NotFoundError`, `RateLimitedError`, `ParseError`). The UI catches that one base class and shows a notification; a last-resort handler in `dispatch()` turns anything else into the same notification, so Kodi always gets an answer. Arguments are validated before any request is sent (`ValueError`).
- **Side effects are injectable:** the HTTP session, clock, `sleep` and randomness are constructor parameters, so tests run instantly and deterministically.

## Rate limiting

RTP Play is a public website, so the client is deliberately conservative (`rtpplay/http.py`):

- **Client-side budget:** `RateLimiter` is a token bucket, by default a burst of 4 requests and then 2 per second. Every request goes through it.
- **Server pushback:** HTTP 429, 502, 503, 504, connection errors and timeouts are retried up to 3 times. Each wait is exponential backoff (`1s, 2s, 4s…`, capped at 30s) with full jitter. Other `requests` errors fail at once as `NetworkError`.
- **`Retry-After`:** when the server sends it (seconds or an HTTP date), it replaces the computed delay. If it asks for more than 30s, the client gives up at once with `RateLimitedError(retry_after=…)` instead of freezing Kodi's UI. The add-on then shows "Try again in N seconds".
- **Total wait budget:** all waits of one request together stay within 30s (`RetryPolicy.max_total_wait`). The client gives up rather than start a wait that would exceed it.
- **No retries for client errors:** 404 raises `NotFoundError`; other unexpected statuses raise immediately.
- **Few requests by design:** categories are a static table (zero requests), and each screen costs one request (opening a single-season show costs two: its program page, then its episodes).

Kodi starts a fresh Python process for every navigation, so the token bucket only spans a single action. That is fine because each action makes a single request (plus at most 3 retries), and the total wait budget bounds how long one action can take. If a feature ever needs many requests per action, the bucket already spaces them out.

The behaviour is pinned by `tests/client/test_rate_limiting.py`. Change those tests deliberately if you change the policy.

## Development setup

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt

pytest                      # all tests
ruff check . && ruff format --check .
python scripts/build_zip.py # dist/plugin.video.modernrtpplay-<version>.zip
```

Exercise the client against the real site without Kodi:

```sh
PYTHONPATH=resources/lib python -c "
from rtpplay import RtpPlayClient
c = RtpPlayClient()
print(c.live_channels()[0])
print(c.episodes(1525).items[0])"
```

To try it in Kodi, build the zip and [install it](INSTALL.md). Alternatively, symlink the repository into Kodi's add-on folder (`~/.kodi/addons/plugin.video.modernrtpplay` on Linux) and restart Kodi; edits then apply on the next navigation. Logs go to `kodi.log`, prefixed with `[plugin.video.modernrtpplay]`.

## How to add a feature

Worked example: a **Podcasts** menu entry. The same steps apply to hubs like Zig Zag or RTP Palco.

1. **Find the data source.** Open the page in a browser with dev tools (here `https://www.rtp.pt/play/podcasts`). Look at the *Network* tab for fragment requests (the site uses `/play/bg_l_*` endpoints, e.g. `bg_l_pd` for podcasts) and note the query parameters. Reproduce it with `curl -A "Mozilla/5.0"`.
2. **Save a fixture.** Trim a real response down to two or three items and store it in `tests/client/fixtures/podcasts.html`. Real markup beats hand-written HTML: it catches the quirks.
3. **Model it.** Reuse an existing model if it fits (a podcast is close to a `Program`). Otherwise add a frozen dataclass to `models.py` and export it from `rtpplay/__init__.py`.
4. **Parse it.** Add `parse_podcasts(fragment)` to `parsers.py` as a pure function, plus tests in `test_parsers.py`. Raise `ParseError` when a page that must have content has none. Return `[]` for an empty list fragment (that is how the site ends pagination).
5. **Expose it.** Add `RtpPlayClient.podcasts(page=1) -> Page[Program]` in `client.py`. Validate arguments before requesting and go through `self._http.get_text`, never `requests` directly, so rate limiting applies. Add a test in `test_client.py` that asserts the exact URL and params.
6. **Show it in Kodi.** In `plugin/views.py`, add a `podcasts` method and register it in `dispatch()`'s action table. Add a root-menu entry if needed. Reuse `_folder`, `_playable`, `_with_next` and `_directory`.
7. **Translate.** Add any new label to both `resources/language/resource.language.en_gb/strings.po` and `…pt_pt/strings.po` (next free id, `#300xx`), and add a constant next to the others in `views.py`.
8. **Test the view.** Extend `FakeClient` in `tests/plugin/test_views.py` and assert the listed URLs/labels. Add `STRINGS` entries in `tests/plugin/conftest.py`.
9. **Document.** Add a line to `CHANGELOG.md` under *Unreleased*, and to the source table above if you used a new endpoint.
10. **Open a pull request.** CI must be green (see below).

### When RTP changes the website

Usually a parser test still passes (old fixture) while the real site fails. To fix it:

1. Reproduce with the snippet above and find the failing method.
2. Download the current page and replace the matching fixture with a trimmed copy.
3. Watch the parser test fail, then update the regex in `parsers.py` until it passes.

Keep markup knowledge inside `parsers.py`. Neither `client.py` nor the UI should change for a markup-only fix.

### Categories

Category ids are a static table in `rtpplay/client.py` (`CATEGORIES`), because discovering them costs one request per category. If RTP adds one, read its id from the category page (`RTPPLAY.currentHPListCategory = 'N'` in `/play/programas/<slug>/canal`) and append it.

## Conventions

- Python 3.8 compatible code (Kodi 20 still ships 3.8 on some platforms): use `from __future__ import annotations` and `typing.List` etc. Ruff's `target-version` only covers syntax, so CI also runs the test suite on a real Python 3.8 (`test-py38`).
- Ruff for lint and formatting (`pyproject.toml`), 100-column lines.
- Branches: `feat/…`, `fix/…`, `docs/…`, `ci/…`. One component or concern per pull request.
- Commits and pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<optional scope>): <imperative summary>`, then a body explaining *why*. Types: `feat` (user-visible feature), `fix` (bug fix), `docs`, `ci`, `test`, `refactor`, `chore`. Scopes name the component: `client`, `addon`, `repo`. Mark breaking changes with `!` (`feat(addon)!: …`). A pull request's title takes the type of its most significant change.

## CI

`.github/workflows/ci.yml` runs on every pull request, on pushes to `main`, and as the first stage of a release.

A pull request runs the full pipeline only when it changes the add-on, its packaging or CI: `resources/`, `main.py`, `addon.xml`, `repository.modernrtpplay/`, `scripts/`, `tests/`, `pyproject.toml`, `requirements*.txt` or `.github/workflows/`. Other pull requests (docs, `CHANGELOG.md`, README) run only `changes` and `site`. Pushes to `main`, manual runs and releases always run everything.

| Job | What it does |
| --- | --- |
| `changes` | Decides whether the full pipeline runs (see above) |
| `site` | Always runs, in seconds. Builds the zip and the GitHub Pages site and checks the site: `addons.xml.md5` matches, every listed zip exists, the repository add-on's URLs share its `datadir`, and `index.html` links the repository zip |
| `lint` | `ruff check`, `ruff format --check` and `mypy`; fails if compiled Python files (`__pycache__/`, `*.pyc`) are committed |
| `test` | `pytest` on Python 3.10 and 3.13 with warnings as errors and a 90% branch-coverage gate |
| `test-py38` | `pytest` on Python 3.8, the oldest Python that Kodi 20 ships |
| `build` | Runs after lint and both test jobs pass. Builds the zip, unpacks it and validates it with `kodi-addon-checker` against Nexus (Kodi 20) and Omega (Kodi 21), so it checks exactly what ships, then uploads the zip as the `addon-zip` artifact. Also builds the repository site and validates the repository add-on |

## Releasing

Releases are published by `.github/workflows/release.yml` when a `v*` tag is pushed:

1. Bump `version` in `addon.xml` ([semantic versioning](https://semver.org)) and update `<news>`.
2. Move the *Unreleased* entries in `CHANGELOG.md` under `## [X.Y.Z] - <date>`.
3. Merge to `main`, then tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.

The workflow then:

1. Checks that the tag matches `addon.xml`'s version and that `CHANGELOG.md` has a section for it.
2. Runs the whole CI workflow (lint, tests, zip build, `kodi-addon-checker`).
3. Builds the Kodi repository from the CI zip (`scripts/build_repo.py`). Its `index.html` is the release index: install steps and every GitHub release, newest first, with links to the notes and zip. Then it creates a GitHub release with the add-on zip, the repository zip and the changelog section as notes.
4. Deploys the repository to GitHub Pages. Installed copies pick up the new version from `addons.xml` there.

Each deploy replaces the site, so it only serves the latest version.

Not automated yet: mirroring `docs/` to the repository wiki, and submitting to the official Kodi repository (`xbmc/action-kodi-addon-submitter`).

The repository add-on (`repository.modernrtpplay/addon.xml`) rarely changes. Bump its version only when its URLs change, and keep the old site URL working until users have updated.

### One-time setup

- *Settings* → *Pages* → *Source*: **GitHub Actions**.
- *Settings* → *Environments* → `github-pages` → *Deployment branches and tags*: add a tag rule `v*`. By default only `main` may deploy, so the `pages` job would be rejected.
