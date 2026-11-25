# advent-calendar
Vibe coded advent calendar to gift your significant other

## Development setup

Use Node.js 24 or newer, pnpm 11.25.0, and `uv` with Python 3.12 or newer.

```sh
pnpm install --frozen-lockfile
uv sync --locked
pnpm typecheck
uv run --locked pytest
```

Pytest starts and stops a local Wrangler server with dummy assets. The tests use temporary state and run without a Cloudflare account. The [implementation plan](plans/01-advent-calendar.md) covers the demo and production stages.

## Prepare gifts

1. Copy the blank [gift template](examples/gifts.json) to `content/gifts.json` and add at least one item per day. Use `note`, `joke`, `song`, `photo`, or `audio` in any combination. Use an HTTPS URL for `song` and a file path relative to `content/` for photos and voice notes. The [demo manifest](src/advent_tools/demo/gifts.json) shows the format.
2. Put any media files in `content/` or a subfolder. Photos can be JPEG, PNG, or WebP. Audio can be MP3, M4A, or WAV. Each file can be up to 10 MiB.
3. Run `uv run --locked python -m advent_tools production` from the repository root. It validates all 24 entries and writes `dist/production/_gifts/`. Fix any errors it reports in `content/gifts.json`, then rerun the command.

Run `uv run --locked python -m advent_tools demo` to build `dist/demo/_gifts/` from the three bundled dummy gifts. The demo uses a sample image, a two-tone audio clip, and a placeholder HTTPS link. Both `content/` and `dist/` are ignored by Git.

## Calendar API

| Request | Behavior |
|---|---|
| `POST /api/session` | Send a JSON object with `passphrase`. Success sets a seven-day session cookie and returns `204`. An incorrect passphrase returns `401`. |
| `GET /api/calendar` | Returns the `day`, `unlocked`, and `today` values for each scheduled door. |
| `GET /api/doors/:day` | Returns `{ day, gift }` for a released door. Returns `403` before release and `404` for a day outside the schedule. |
| `GET` or `HEAD /api/doors/:day/photo` or `/audio` | Serves the selected media for a released door. Single byte ranges let the browser seek in audio. |

Calendar, gift, and media routes require the session cookie. A released gift provides the protected `photo` or `audio` URL when it contains that media. The three demo doors release November 28–30. The 24 production doors release December 1–24. Each release happens at midnight in `Europe/Rome`, and earlier doors stay open.

Each deployment sets `CALENDAR_SCHEDULE` to `demo` or `production` and supplies separate `CALENDAR_PASSPHRASE` and `SESSION_SIGNING_KEY` secrets. Generate each signing key from at least 32 random bytes. A `SIGN_IN_LIMITER` binding allows five sign-in submissions per client IP per minute per Cloudflare location. Use a distinct limiter namespace for each deployment. Keep Worker-first asset routing enabled to protect the internal `/_gifts/` directory.
