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

## Calendar API

| Request | Behavior |
|---|---|
| `POST /api/session` | Send a JSON object with `passphrase`. Success sets a seven-day session cookie and returns `204`. An incorrect passphrase returns `401`. |
| `GET /api/calendar` | Returns the `day`, `unlocked`, and `today` values for each scheduled door. |
| `GET /api/doors/:day` | Returns `{ day, gift }` for a released door. Returns `403` before release and `404` for a day outside the schedule. |

Both GET routes require the session cookie. The three demo doors release November 28–30. The 24 production doors release December 1–24. Each release happens at midnight in `Europe/Rome`, and earlier doors stay open.

Each deployment sets `CALENDAR_SCHEDULE` to `demo` or `production` and supplies separate `CALENDAR_PASSPHRASE` and `SESSION_SIGNING_KEY` secrets. Generate each signing key from at least 32 random bytes. A `SIGN_IN_LIMITER` binding allows five sign-in submissions per client IP per minute per Cloudflare location. Use a distinct limiter namespace for each deployment. Keep Worker-first asset routing enabled to protect the internal `/_gifts/` directory.
