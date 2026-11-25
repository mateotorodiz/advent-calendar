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
