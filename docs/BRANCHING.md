# Branching and releases

`main` is the trunk. Every change reaches it first, through a pull request. Releases are cut from `main` into `release/X.Y` branches, and every published version is a `vX.Y.Z` tag on one of them.

```
              feat/…                 fix/…
             ●───●                   ●
            ╱     ╲                 ╱ ╲
main  ──●──●───────●───R1───●──────●───F───●───R2──▶
                       │               ┆        │
                       │        cherry-pick -x  │
                       │               ┆        │
release/0.2            └───────────────F'──B    └──▶ release/0.3
                    v0.2.0              v0.2.1      v0.3.0

R1, R2: release PRs (version bump, changelog)   F: squashed fix   B: patch bump
```

## Branches

| Branch | Cut from | Merges into | Lifetime |
| --- | --- | --- | --- |
| `main` | — | — | Permanent. Always green, always releasable. |
| `feat/…`, `fix/…`, `docs/…`, `ci/…` | `main` | `main` | Days. Deleted after merge. |
| `release/X.Y` | `main`, at the commit that becomes `vX.Y.0` | nothing (receives cherry-picks) | Until the next minor release. Kept afterwards, read-only. |

- **Names:** `<type>/<short-kebab-summary>`, e.g. `fix/season-parsing`. The prefix is the Conventional Commits type of the main change (`feat`, `fix`, `docs`, `ci`; `test`, `refactor` and `chore` work the same way).
- **One concern per branch.** Rebase on `main` rather than merging `main` in, and keep branches short so they never drift far.
- **No long-lived integration branches** (`develop`, `next`). Unfinished work stays on its branch or ships hidden.

## Merging

- **Pull requests only.** Nothing is pushed straight to `main` or `release/*`.
- **Squash merge** feature branches, so each PR becomes one commit on `main`. The PR title is that commit's subject, so it must follow Conventional Commits as described in [DEVELOPING.md](DEVELOPING.md#conventions): `type(scope): imperative summary`, scopes `client`, `addon`, `repo`, `!` for breaking changes (`feat(addon)!: …`).
- **Green CI required:** `changes`, `site`, `lint`, `test`, `test-py38` and `build`. Docs-only PRs skip the add-on jobs, and GitHub counts a skipped required check as passed.
- **Changelog in the same PR:** user-visible changes add a line under *Unreleased* in `CHANGELOG.md`.

## Releases

### Minor or major release (`X.Y.0`)

1. On `main`, open a PR `chore(addon): release X.Y.0` that bumps `version` in `addon.xml`, updates `<news>`, and moves the *Unreleased* entries under `## [X.Y.0] - <date>`, leaving an empty *Unreleased* heading.
2. After it merges, cut the branch from that commit and tag it:

   ```bash
   git switch -c release/X.Y <merge commit> && git push -u origin release/X.Y
   git tag -a vX.Y.0 -m "vX.Y.0" && git push origin vX.Y.0
   ```

3. The tag triggers the release workflow (see *Releasing* in [DEVELOPING.md](DEVELOPING.md)).

### Patch release (`X.Y.Z`)

**Fixes go to `main` first, then are cherry-picked to the release branch.** Never the other way round: fixing on `main` first guarantees the next minor release cannot regress, keeps one direction of flow, and avoids merging release branches back into the trunk.

1. Fix on a `fix/…` branch off `main`, PR, squash-merge as usual.
2. Cherry-pick the squashed commit onto a branch off `release/X.Y` and open a PR against `release/X.Y`:

   ```bash
   git switch -c fix/0.2-season-parsing origin/release/0.2
   git cherry-pick -x <commit on main>
   ```

   `-x` records the original commit, so the two are traceable.
3. In the same PR (or a follow-up `chore(addon): release X.Y.Z` PR), bump `addon.xml` to `X.Y.Z` and add `## [X.Y.Z] - <date>` to `CHANGELOG.md` with the fix's entry.
4. Merge, then tag the tip of `release/X.Y` with `vX.Y.Z` and push the tag.
5. Forward the changelog: a `docs: add X.Y.Z to changelog` PR on `main` adds the `## [X.Y.Z]` section and removes that entry from *Unreleased*, so `main`'s changelog stays the complete history. `main`'s `addon.xml` version is left alone.

### Hotfix

A hotfix is a patch release done right away: same steps, no batching. Only if `main` has moved on so far that the fix no longer applies (the code was rewritten) do you branch from `release/X.Y` directly. Then say so in the PR, and open a matching PR on `main` if the bug still exists there.

### Which branches get patches

Only the **latest** `release/X.Y`. Older release branches are frozen: users get fixes by updating to the latest minor. The Kodi repository on GitHub Pages only serves one version anyway (see below).

## Versions and tags

- [Semantic versioning](https://semver.org). From the commits since the last release: any `!` → major, any `feat` → minor, otherwise patch. While on `0.x`, breaking changes bump the minor.
- `addon.xml`'s `version`, the `CHANGELOG.md` heading and the tag always agree; the release workflow refuses a tag that doesn't match.
- Tags are annotated, `vX.Y.Z`, and only ever placed on a `release/X.Y` commit. They are never moved or deleted: a broken release is fixed by the next patch.

## Branch protection (GitHub settings)

- **`main` and `release/*`** (one ruleset each): require a pull request, require the status checks `changes`, `site`, `lint`, `test`, `test-py38`, `build`, require branches to be up to date, block force pushes and deletion.
- **`main`:** allow squash merge only, and enable *Automatically delete head branches*.
- **Tags `v*`** (tag ruleset): only maintainers may create them; block updates and deletion.

## Fit with the release pipeline

`release.yml` (on `main`) runs on any `v*` tag, whatever branch it points at, so it already works with release branches. It checks that the tag matches `addon.xml` and `CHANGELOG.md`, runs CI, creates the GitHub release and deploys the Kodi repository to Pages. The `github-pages` environment's `v*` tag rule covers tags on release branches.

Still open:

- **`ci.yml`** runs on pushes to `main` only. Add `release/**` to `on.push.branches` so release branches get the same checks after a merge (pull requests against them already run CI).
- **Pages deploy:** each deploy replaces the site. The "latest release line only" rule above keeps this safe by convention; a guard that skips the `pages` job unless the tag is the highest `v*` tag would enforce it.
- **`check-version`** doesn't check where the tag points. Optionally fail unless the tagged commit is on `origin/release/X.Y`.

## Adopting it now

`release/0.2` was cut at `0304106`, the merge of #13, rather than at the #12 version bump (`7bcbb25`). Both are version 0.2.0 with the same add-on code, but the release workflow runs from the tagged commit, so cutting after #13 gives the first release the release index page and path-filtered CI. The 20-minute build timeout (#16) is cherry-picked onto it before `v0.2.0` is tagged.
