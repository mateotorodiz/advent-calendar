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

## Preview the calendar

```sh
uv run --locked python -m advent_tools demo
pnpm build:web demo
pnpm exec wrangler dev src/worker/index.ts --local --config tests/fixtures/wrangler.jsonc --assets ./dist/demo
```

Open the local URL Wrangler prints in a browser and use `fixture-passphrase`. This preview uses the current time. The optional mobile browser tests use a fixed clock to exercise all three demo days immediately.

```sh
uv run --locked --group browser playwright install chromium
uv run --locked --group browser pytest
```

## Prepare gifts

### 1. Set up your private content folder

From PowerShell in the repository, run these commands once to create the folder and copy the [blank 24-day template](examples/gifts.json). If `content/gifts.json` already exists, keep editing that copy.

```powershell
New-Item -ItemType Directory -Force content/media | Out-Null
if (-not (Test-Path -LiteralPath content/gifts.json)) {
    Copy-Item -LiteralPath examples/gifts.json -Destination content/gifts.json
}
```

### 2. Add a gift for each day

Open `content/gifts.json` in a text editor. Keep exactly one entry for every day from `1` through `24`. Each entry needs at least one of the fields below. You can combine fields or leave optional ones out.

| Field | What to put in it |
|---|---|
| `note` | Your own note or appreciation message as text |
| `joke` | Your own joke as text |
| `photo` | A JPEG, PNG, or WebP path such as `media/day-02.jpg` |
| `audio` | An MP3, M4A, or WAV path such as `media/day-03.m4a` |
| `song` | A song link beginning with `https://` |

For example, you can replace the first few entries with something in this format. Keep the remaining entries in your file and fill them in too.

```json
[
  { "day": 1, "note": "Your own message here" },
  { "day": 2, "photo": "media/day-02.jpg", "note": "Your own caption here" },
  { "day": 3, "audio": "media/day-03.m4a" },
  { "day": 4, "song": "https://example.com/your-song" }
]
```

Put each referenced photo or voice note in `content/media/`. Paths in the JSON are relative to `content/`, and each file can be up to 10 MiB. You can edit in any order. Day 1 opens on December 1 and day 24 opens on December 24, each at midnight in Italy.

### 3. Validate and build the production bundle

```powershell
uv run --locked python -m advent_tools production
pnpm.cmd build:web production
```

The first command validates the 24 gifts and writes `dist/production/_gifts/`. If it reports an error, fix the indicated entry or file in `content/` and run it again. The second command adds the public pages to `dist/production/`. Both commands run locally. `content/` and `dist/` are ignored by Git.

Run `uv run --locked python -m advent_tools demo` to build `dist/demo/_gifts/` from the three bundled dummy gifts. The demo uses a sample image, a two-tone audio clip, and a link to [Kevin MacLeod’s recording of *Dance of the Sugar Plum Fairy*](https://commons.wikimedia.org/wiki/File:Dance_of_the_Sugar_Plum_Fairy_(ISRC_USUAN1100625).mp3).

## Host the three-day demo

1. Run `pnpm exec wrangler login` and finish Cloudflare sign-in in the browser. Set up a `workers.dev` subdomain in the Workers dashboard if the account needs one.
2. Build the public UI and bundled dummy gifts, then validate the deploy configuration.

   ```sh
   uv run --locked python -m advent_tools demo
   pnpm build:web demo
   pnpm exec wrangler deploy --config wrangler.demo.jsonc --dry-run
   ```

3. Create an ignored `.dev.vars.demo` file with `CALENDAR_PASSPHRASE` and `SESSION_SIGNING_KEY`. Choose a demo-only passphrase and generate the signing key from at least 32 random bytes. Deploy both as Cloudflare secrets.

   ```sh
   pnpm exec wrangler deploy --config wrangler.demo.jsonc --secrets-file .dev.vars.demo
   ```

4. Use the HTTPS origin printed by Wrangler in `uv run --locked python -m advent_tools.demo_check <demo-origin>`. The command prompts for the passphrase and checks the published demo against the current date. Run the [phone checklist](plans/01-advent-calendar.md#stage-5--three-day-hosted-demo) through November 30.

## Calendar API

| Request | Behavior |
|---|---|
| `POST /api/session` | Send a JSON object with `passphrase`. Success sets a seven-day session cookie and returns `204`. An incorrect passphrase returns `401`. |
| `GET /api/calendar` | Returns the `day`, `unlocked`, and `today` values for each scheduled door. |
| `GET /api/doors/:day` | Returns `{ day, gift }` for a released door. Returns `403` before release and `404` for a day outside the schedule. |
| `GET` or `HEAD /api/doors/:day/photo` or `/audio` | Serves the selected media for a released door. Single byte ranges let the browser seek in audio. |

Calendar, gift, and media routes require the session cookie. A released gift provides the protected `photo` or `audio` URL when it contains that media. The three demo doors release November 28–30. The 24 production doors release December 1–24. Each release happens at midnight in `Europe/Rome`, and earlier doors stay open.

Each deployment sets `CALENDAR_SCHEDULE` to `demo` or `production` and supplies separate `CALENDAR_PASSPHRASE` and `SESSION_SIGNING_KEY` secrets. Generate each signing key from at least 32 random bytes. A `SIGN_IN_LIMITER` binding allows five sign-in submissions per client IP per minute per Cloudflare location. Use a distinct limiter namespace for each deployment. Keep Worker-first asset routing enabled to protect the internal `/_gifts/` directory.
