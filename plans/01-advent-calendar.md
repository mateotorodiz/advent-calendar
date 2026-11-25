# Advent Calendar Implementation Plan

Follow the [coder workflow](../skills/coder-workflow/SKILL.md) for each stage. Start each stage from `main` on its own branch and merge it into `main` once its exit checks pass. All dates are in 2026 and use `Europe/Rome`.

## Design decision

Send one HTTPS link to a phone-friendly calendar protected by a shared passphrase. Use Cloudflare Workers with separate demo and production deployments. A server-side date check releases one new gift at midnight on each scheduled day. Earlier gifts stay available. Production releases are December 1–24. Demo releases are November 28–30.

The TypeScript Worker serves the website and controls access to gift data and media. On-demand checks against the server clock avoid the need for a scheduler or database. Python prepares content and tests the real Worker over HTTP. The proposed deployment uses the free Workers plan and a `workers.dev` address.

```text
src/worker/           TypeScript routes, sessions, unlocks, media
src/web/              Mobile UI and browser interactions
src/advent_tools/     Python content validation and packaging
tests/                Pytest suite and dummy fixtures
examples/             Blank gift template and sample entries
content/              Real gifts and media, ignored by Git
```

## Stage 1 · Project setup

- Fetch GitHub’s existing `main` and base the implementation branch on it, carrying over the local workflow skill and this plan. Use local fixtures and keep real gifts, secrets, and generated deployment bundles out of Git from the start.
- Set up the Python `src` package with `uv`, `pyproject.toml`, and `uv.lock`. Lock Node dependencies for TypeScript and Wrangler. Use Pydantic for gift manifests and HTTPX with pytest for Worker requests.
- Add a pytest fixture that starts local Wrangler with dummy assets, waits until the Worker is reachable, and shuts it down after the suite.
- **Exit check.** A clean checkout can install from both lockfiles and run `uv run --locked pytest` against the local Worker.
- **Verified.** A fresh copy installed from both lockfiles, passed `pnpm typecheck`, and passed all three pytest checks. The Worker smoke tests cover the JSON health response and a dummy asset.

## Stage 2 · Calendar dates and access

- Write failing HTTP tests for the scheduled release boundaries, earlier doors, wrong passphrases, expired or invalid cookies, and repeated failed sign-in attempts.
- Implement `POST /api/session`, `GET /api/calendar`, and `GET /api/doors/:day`. Store the passphrase and signing key as hosting secrets. Limit repeated guesses and use a signed, expiring `Secure`, `HttpOnly`, `SameSite=Lax` cookie.
- Evaluate release dates using the server clock and `Europe/Rome`. Inject a fixed clock only in the local test harness. The public deployments use the actual time and separate schedules, secrets, and asset bundles.
- **Exit check.** Tests cover one second before and exactly at midnight for each scheduled door, including the first and last December dates. Calendar responses expose door states only. Each protected route rejects an invalid session and withholds future gifts from signed-in visitors.
- **Verified.** Local HTTP tests cover all 27 release boundaries, earlier doors, expired and invalid cookies, repeated guesses, and direct requests for the private gift manifest. A separate local HTTPS check uses the release Worker entry point with the production schedule and sends the secure cookie automatically. The release entry point ignores the test clock and schedule headers.

## Stage 3 · Gift preparation and protected media

- Write validation tests for missing or duplicate days, empty gifts, malformed song links, and missing or out-of-folder media files. One entry per day can contain a note or joke, a shared photo, a voice note, a song link, or a combination. You supply all real content.
- Build one command to validate and package gifts from the local content folder. Require three complete entries for the demo and all 24 entries for production.
- Serve photos and audio only after the Worker verifies both the session and the release date. Route direct asset requests through the Worker, deny access to internal asset paths, and mark protected responses `private, no-store`.
- **Exit check.** Tests confirm unauthenticated and early media requests fail, internal asset paths are inaccessible, and authorized audio range requests work for seeking. The demo build includes dummy assets only.
- **Verified.** The packaging command validates the required 3 or 24 days and keeps the previous bundle when validation fails. Local Wrangler tests serve the packaged demo image and audio after release, reject direct internal asset requests, and verify byte-range responses for audio seeking.

## Stage 4 · Phone experience

- Build the passphrase screen, the 24-door grid, and the gift view. Highlight today’s door, show which doors are locked, and let the visitor return to gifts that have already been released.
- Refresh availability when the page regains focus or becomes visible. Use the browser’s native audio controls and a regular link for songs.
- **Exit check.** Verify the passphrase, door navigation, error feedback, and media controls at a mobile viewport. Check the actual chat app and phone during the hosted demo.
- **Verified.** Chrome at mobile viewports exercised incorrect and correct passphrases, refresh across Rome midnight, navigation and bookmarks, and the session expiration flow. The demo photo loaded, its audio played and supported seeking, and the song appeared as a regular link. All 24 production doors fit a 320-pixel viewport.

## Stage 5 · Three-day hosted demo

Target a demo handoff on November 27, subject to plan approval and Cloudflare access. Use a separate URL, passphrase, and dummy gifts. The same Worker and UI code will run in production.

| Date | Expected behavior and phone checks |
|---|---|
| November 27 | All doors are locked. The link opens from the intended chat app and prompts for a passphrase. |
| November 28 | Door 1 opens. Try a wrong passphrase, then sign in and view the note and photo. Verify door 2 and its media stay locked. |
| November 29 | Door 2 opens and door 1 still works. Check that the same browser remembers the session. Play, pause, and seek in a voice note. Check that a direct gift link requires sign-in in a private tab. |
| November 30 | Door 3 opens when returning to a tab left open overnight. Follow the song link and return to the calendar. Revisit earlier doors and confirm the demo ends at door 3. |

**Exit check.** Record the result of each phone check. Fix any failures in a red–green–refactor cycle and rerun the affected checks before release.

## Stage 6 · Production handoff

- Validate all 24 entries, preview the real content locally, and open song links and play media on the intended device. Keep a short setup and deployment guide in the repo.
- Deploy with the December schedule and a separate production passphrase. Run a smoke test before December 1 to check the passphrase and the all-locked state. Rerun the full pytest suite against the release configuration and record the results.
- **Exit check.** All automated checks and the three-day phone demo pass, the real calendar is reachable, and the all-locked state is verified. Share the link and passphrase with the user for delivery.
