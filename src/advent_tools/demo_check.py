import argparse
from datetime import date, datetime, timedelta, timezone
from getpass import getpass
from secrets import token_urlsafe
from urllib.parse import urlsplit

import httpx

from advent_tools.gifts import DAY_COUNTS


class SmokeCheckError(ValueError):
    pass


def expect_status(response: httpx.Response, status: int) -> None:
    if response.status_code != status:
        request = response.request
        raise SmokeCheckError(
            f"{request.method} {request.url.path}: expected {status}, received {response.status_code}"
        )


def check_demo(client: httpx.Client, passphrase: str, *, now: datetime | None = None) -> int:
    """Check the published demo without overriding its schedule or clock."""
    for path in ("/", "/calendar.css", "/calendar.js"):
        expect_status(client.get(path), 200)
    for path in ("/api/calendar", "/api/doors/1", "/api/doors/1/photo", "/api/doors/2/audio"):
        expect_status(client.get(path), 401)

    expect_status(client.post("/api/session", json={"passphrase": token_urlsafe(24)}), 401)
    expect_status(client.post("/api/session", json={"passphrase": passphrase}), 204)
    for path in ("/_gifts/manifest.json", "/_gifts/1/photo.png", "/_gifts/2/audio.wav"):
        expect_status(client.get(path), 404)

    response = client.get("/api/calendar")
    expect_status(response, 200)
    # The fixed demo dates fall in Italy's UTC+1 winter period.
    italy = timezone(timedelta(hours=1))
    local_day = (now or datetime.now(timezone.utc)).astimezone(italy).date()
    expected = [
        {"day": day, "releaseDate": release.isoformat(), "unlocked": local_day >= release,
         "today": local_day == release}
        for day, release in enumerate((date(2026, 11, day) for day in range(25, 31)), start=1)
    ]
    # Older demo deployments sent the same state without release dates.
    legacy = [{key: value for key, value in door.items() if key != "releaseDate"} for door in expected]
    if response.json() not in ({"doors": expected}, {"doors": legacy}):
        raise SmokeCheckError("Door states do not match the November 25–30 Rome schedule.")

    for door in expected:
        status = 200 if door["unlocked"] else 403
        expect_status(client.get(f"/api/doors/{door['day']}"), status)
    expect_status(client.get("/api/doors/7"), 404)
    for day in (1, 4):
        expect_status(client.get(f"/api/doors/{day}/photo"), 200 if expected[day - 1]["unlocked"] else 403)
    for day in (2, 5):
        unlocked = expected[day - 1]["unlocked"]
        audio = client.get(f"/api/doors/{day}/audio", headers={"Range": "bytes=0-1"})
        expect_status(audio, 206 if unlocked else 403)
        if unlocked and (audio.content != b"RI" or not audio.headers.get("content-range", "").startswith("bytes 0-1/")):
            raise SmokeCheckError(f"Door {day} audio did not return the requested two bytes.")
    return sum(door["unlocked"] for door in expected)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the hosted Advent Calendar demo.")
    parser.add_argument("url", help="HTTPS origin of the demo Worker")
    args = parser.parse_args()
    url = urlsplit(args.url)
    if (url.scheme != "https" or not url.hostname or url.username is not None
            or url.password is not None or url.query or url.fragment or url.path not in ("", "/")):
        parser.error("use the demo's HTTPS origin without a path or credentials")

    passphrase = getpass("Demo passphrase: ")
    try:
        with httpx.Client(base_url=args.url, timeout=15) as client:
            opened = check_demo(client, passphrase)
    except (SmokeCheckError, httpx.HTTPError) as error:
        parser.exit(1, f"Demo check failed: {error}\n")
    print(f"Demo smoke check passed. {opened} of {DAY_COUNTS['demo']} doors open.")


if __name__ == "__main__":
    main()
