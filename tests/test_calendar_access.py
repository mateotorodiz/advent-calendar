from datetime import datetime, timedelta, timezone

import httpx
import pytest


PASSPHRASE = "fixture-passphrase"
COOKIE = "__Host-advent_session"
ROME = timezone(timedelta(hours=1))  # These releases all fall in Italian winter time.
BASE_TIME = datetime(2026, 11, 24, 12, tzinfo=ROME)


@pytest.fixture
def client(worker_url, request):
    yield from fixed_time_client(worker_url, request)


@pytest.fixture
def demo_client(packaged_demo_worker_url, request):
    yield from fixed_time_client(packaged_demo_worker_url, request)


def fixed_time_client(url, request):
    with httpx.Client(base_url=url, timeout=5, trust_env=False) as client:
        set_time(client, BASE_TIME)
        client.headers["x-fixture-client"] = request.node.nodeid
        yield client


def set_time(client, time):
    client.headers["x-fixture-time"] = time.astimezone(timezone.utc).isoformat()


def sign_in(client, passphrase=PASSPHRASE):
    return client.post("/api/session", json={"passphrase": passphrase})


def authenticate(client):
    response = sign_in(client)
    assert response.status_code == 204
    client.headers["Cookie"] = f"{COOKIE}={response.cookies[COOKIE]}"
    client.cookies.clear()  # HTTP loopback cannot send a Secure cookie automatically.
    return response


@pytest.mark.parametrize("path", ["/api/calendar", "/api/doors/1"])
def test_protected_routes_require_a_session(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "private, no-store"


def test_sign_in_sets_a_private_expiring_cookie(client):
    response = authenticate(client)
    cookie = response.headers["set-cookie"].lower()
    assert all(flag in cookie for flag in ("; secure", "; httponly", "; samesite=lax", "; path=/"))
    assert "; max-age=604800" in cookie
    assert "; domain=" not in cookie
    assert response.headers["cache-control"] == "private, no-store"
    assert client.get("/api/calendar").status_code == 200


def test_wrong_passphrase_is_throttled(client):
    for _ in range(5):
        response = sign_in(client, "wrong passphrase")
        assert response.status_code == 401
        assert "set-cookie" not in response.headers

    response = sign_in(client)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("payload", ["{", "null", '{"passphrase":3}', '"' + "x" * 1024 + '"'])
def test_sign_in_rejects_invalid_payloads(client, payload):
    response = client.post("/api/session", content=payload, headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("session_problem", ["malformed", "tampered", "expires_now"])
def test_invalid_sessions_are_rejected_on_both_routes(client, session_problem):
    authenticate(client)
    if session_problem == "expires_now":
        set_time(client, BASE_TIME + timedelta(days=7) - timedelta(seconds=1))
        assert client.get("/api/calendar").status_code == 200
        set_time(client, BASE_TIME + timedelta(days=7))
    elif session_problem == "malformed":
        client.headers["Cookie"] = f"{COOKIE}=bad"
    else:
        name_and_expiry, signature = client.headers["Cookie"].split(".")
        first = "A" if signature[0] != "A" else "B"
        client.headers["Cookie"] = f"{name_and_expiry}.{first}{signature[1:]}"

    assert client.get("/api/calendar").status_code == 401
    assert client.get("/api/doors/1").status_code == 401


@pytest.mark.parametrize(
    ("schedule", "first_day", "count", "day"),
    [("demo", datetime(2026, 11, 25, tzinfo=ROME), 6, day) for day in range(1, 7)]
    + [("production", datetime(2026, 12, 1, tzinfo=ROME), 24, day) for day in range(1, 25)],
)
def test_each_door_releases_at_rome_midnight(client, schedule, first_day, count, day):
    client.headers["x-fixture-schedule"] = schedule
    midnight = first_day + timedelta(days=day - 1)
    set_time(client, midnight - timedelta(seconds=1))
    authenticate(client)

    assert client.get("/api/calendar").json() == {
        "doors": [
            {"day": number, "releaseDate": (first_day + timedelta(days=number - 1)).date().isoformat(),
             "unlocked": number < day, "today": number == day - 1}
            for number in range(1, count + 1)
        ]
    }
    early = client.get(f"/api/doors/{day}")
    assert early.status_code == 403
    assert early.json() == {"error": "door_locked"}
    assert early.headers["cache-control"] == "private, no-store"

    set_time(client, midnight)
    response = client.get("/api/calendar")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == {
        "doors": [
            {"day": number, "releaseDate": (first_day + timedelta(days=number - 1)).date().isoformat(),
             "unlocked": number <= day, "today": number == day}
            for number in range(1, count + 1)
        ]
    }
    opened = client.get(f"/api/doors/{day}")
    assert opened.status_code == 200
    assert opened.json() == {"day": day, "gift": {"note": f"Fixture gift {day}"}}
    assert opened.headers["cache-control"] == "private, no-store"
    if day > 1:
        assert client.get(f"/api/doors/{day - 1}").status_code == 200


def test_demo_has_no_seventh_gift_and_earlier_doors_stay_open(client):
    client.headers["x-fixture-schedule"] = "demo"
    set_time(client, datetime(2026, 12, 1, tzinfo=ROME))
    authenticate(client)

    assert client.get("/api/doors/7").status_code == 404
    assert client.get("/api/doors/1").status_code == 200
    assert client.get("/api/calendar").json() == {
        "doors": [
            {"day": day, "releaseDate": f"2026-11-{day + 24}", "unlocked": True, "today": False}
            for day in range(1, 7)
        ]
    }


@pytest.mark.parametrize(
    "path",
    ["/_gifts/manifest.json", "/%5Fgifts/manifest.json", "/_gifts%2Fmanifest.json", "/%2F_gifts/manifest.json"],
)
def test_the_gift_manifest_cannot_be_read_via_static_assets(client, path):
    assert client.get(path).status_code == 404


def test_unknown_api_path_does_not_fall_back_to_assets(client):
    assert client.get("/api/missing").json() == {"error": "not_found"}


def test_media_routes_require_a_session(client):
    set_time(client, datetime(2026, 11, 29, tzinfo=ROME))
    for path in ("/api/doors/1/photo", "/api/doors/2/audio"):
        response = client.get(path, headers={"Range": "bytes=0-1"})
        assert response.status_code == 401
        assert response.headers["cache-control"] == "private, no-store"


def test_packaged_demo_media_unlocks_with_its_own_door(demo_client):
    authenticate(demo_client)
    photo = "/api/doors/1/photo"
    audio = "/api/doors/2/audio"
    assert demo_client.get(photo).status_code == 403
    assert demo_client.head(audio).status_code == 403

    set_time(demo_client, datetime(2026, 11, 25, tzinfo=ROME))
    assert demo_client.get("/api/doors/1").json()["gift"]["photo"] == photo
    response = demo_client.get(photo)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert demo_client.get(audio).status_code == 403
    assert demo_client.get("/api/doors/1/audio").status_code == 404

    set_time(demo_client, datetime(2026, 11, 26, tzinfo=ROME))
    assert demo_client.get("/api/doors/2").json() == {"day": 2, "gift": {"audio": audio}}
    assert demo_client.get(photo).status_code == 200
    for path in ("/_gifts/2/audio.wav", "/%5Fgifts/2/audio.wav", "/_gifts%2F2/audio.wav"):
        assert demo_client.get(path).status_code == 404

    del demo_client.headers["Cookie"]
    assert demo_client.get(audio).status_code == 401


def test_audio_supports_browser_byte_ranges(demo_client):
    set_time(demo_client, datetime(2026, 11, 26, tzinfo=ROME))
    authenticate(demo_client)
    path = "/api/doors/2/audio"
    full = demo_client.get(path)
    assert full.status_code == 200
    assert full.headers["content-type"] == "audio/wav"
    assert full.content.startswith(b"RIFF")
    length = len(full.content)
    for value, start, end in (("0-1", 0, 1), ("12-", 12, length - 1), ("-4", length - 4, length - 1)):
        partial = demo_client.get(path, headers={"Range": f"bytes={value}"})
        assert partial.status_code == 206
        assert partial.headers["content-range"] == f"bytes {start}-{end}/{length}"
        assert partial.headers["content-length"] == str(end - start + 1)
        assert partial.headers["cache-control"] == "private, no-store"
        assert partial.content == full.content[start:end + 1]

    impossible = demo_client.get(path, headers={"Range": f"bytes={length}-"})
    assert impossible.status_code == 416
    assert impossible.headers["content-range"] == f"bytes */{length}"
    assert impossible.headers["cache-control"] == "private, no-store"
    head = demo_client.head(path)
    assert head.status_code == 200
    assert head.headers["accept-ranges"] == "bytes"
    if "content-length" in head.headers:
        assert head.headers["content-length"] == str(length)
    assert not head.content


def test_release_entry_uses_real_clock_and_cookie_over_https(release_worker_url):
    with httpx.Client(base_url=release_worker_url, timeout=5, trust_env=False, verify=False) as client:
        assert sign_in(client).status_code == 204
        client.headers["x-fixture-schedule"] = "demo"
        set_time(client, datetime(2000, 1, 1, tzinfo=ROME))
        first = client.get("/api/calendar")
        assert first.status_code == 200
        assert len(first.json()["doors"]) == 24
        set_time(client, datetime(2099, 1, 1, tzinfo=ROME))
        assert client.get("/api/calendar").json() == first.json()
