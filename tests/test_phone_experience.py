import os

import pytest

playwright = pytest.importorskip("playwright.sync_api", reason="Install the optional browser test group.")
expect = playwright.expect


@pytest.fixture(scope="module")
def chromium():
    with playwright.sync_playwright() as manager:
        browser = manager.chromium.launch(channel=os.environ.get("ADVENT_TEST_BROWSER"))
        yield browser
        browser.close()


@pytest.fixture
def phone(chromium):
    with chromium.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                              has_touch=True, ignore_https_errors=True) as context:
        page = context.new_page()
        page.set_default_timeout(5000)
        yield page


def use_time(page, case, time, schedule="demo"):
    page.set_extra_http_headers({"x-fixture-time": time, "x-fixture-client": case,
                                 "x-fixture-schedule": schedule})


def sign_in(page, passphrase="fixture-passphrase"):
    page.get_by_label("Passphrase").fill(passphrase)
    page.get_by_role("button", name="Unlock calendar").click()


def test_phone_flow(phone, browser_worker_url):
    use_time(phone, "phone-flow", "2026-11-24T22:59:59Z")
    assert phone.goto(browser_worker_url).ok
    sign_in(phone, "incorrect")
    expect(phone.get_by_role("alert")).to_have_text("That passphrase didn’t match. Try again.")
    sign_in(phone)
    expect(phone.get_by_role("button", name="Door 1, locked")).to_be_disabled()

    use_time(phone, "phone-flow", "2026-11-24T23:00:00Z")
    phone.evaluate("dispatchEvent(new Event('focus'))")
    phone.get_by_role("button", name="Door 1, today").click()
    expect(phone.get_by_role("heading", name="Door 1")).to_be_visible()
    photo = phone.get_by_role("img", name="Photo for door 1")
    expect(photo).to_be_visible()
    phone.wait_for_function("document.querySelector('.gift-photo')?.naturalWidth > 0")
    phone.get_by_role("link", name="Back to calendar").click()
    expect(phone.get_by_role("button", name="Door 1, today")).to_be_focused()
    expect(phone.get_by_role("button", name="Door 2, locked")).to_be_disabled()

    use_time(phone, "phone-flow", "2026-11-25T23:00:00Z")
    phone.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    phone.get_by_role("button", name="Door 2, today").click()
    expect(phone.get_by_role("heading", name="Door 2")).to_be_visible()
    audio = phone.locator("audio[controls]")
    expect(audio).to_be_visible()
    phone.wait_for_function("document.querySelector('audio')?.duration > 1")
    audio.evaluate("element => element.play()")
    phone.wait_for_function("document.querySelector('audio')?.currentTime > 0")
    audio.evaluate("element => element.pause()")
    audio.evaluate("element => element.currentTime = 1")
    phone.wait_for_function("document.querySelector('audio')?.currentTime >= 1")
    phone.go_back()
    expect(phone.get_by_role("button", name="Door 1, open")).to_be_enabled()
    assert phone.locator("audio").count() == 0

    use_time(phone, "phone-flow", "2026-11-26T23:00:00Z")
    phone.evaluate("dispatchEvent(new Event('focus'))")
    phone.get_by_role("button", name="Door 3, today").click()
    expect(phone.get_by_role("link", name="Listen to the song")).to_have_attribute(
        "href", "https://commons.wikimedia.org/wiki/File:Dance_of_the_Sugar_Plum_Fairy_(ISRC_USUAN1100625).mp3",
    )


def test_gift_bookmark_requires_sign_in_and_survives_reload(phone, browser_worker_url):
    use_time(phone, "bookmark", "2026-11-24T23:00:00Z")
    phone.goto(f"{browser_worker_url}/#door-1")
    expect(phone.get_by_role("img", name="Photo for door 1")).to_have_count(0)
    sign_in(phone)
    expect(phone.get_by_role("heading", name="Door 1")).to_be_visible()
    phone.reload()
    expect(phone.get_by_role("img", name="Photo for door 1")).to_be_visible()


def test_production_grid_fits_small_phone(phone, browser_worker_url):
    phone.set_viewport_size({"width": 320, "height": 700})
    use_time(phone, "production-grid", "2026-11-30T22:59:59Z", "production")
    phone.goto(browser_worker_url)
    sign_in(phone)
    expect(phone.get_by_role("button", name=r"Door 24, locked")).to_be_disabled()
    expect(phone.locator(".door")).to_have_count(24)
    assert phone.evaluate("innerWidth === 320 && document.documentElement.scrollWidth === innerWidth")


def test_expired_session_clears_an_open_gift(phone, browser_worker_url):
    use_time(phone, "expired", "2026-11-24T23:00:00Z")
    phone.goto(f"{browser_worker_url}/#door-1")
    sign_in(phone)
    expect(phone.get_by_role("img", name="Photo for door 1")).to_be_visible()

    use_time(phone, "expired", "2026-12-01T23:00:00Z")
    phone.evaluate("dispatchEvent(new Event('focus'))")
    expect(phone.get_by_role("alert")).to_have_text("Your session ended. Enter the passphrase again.")
    expect(phone.get_by_role("img", name="Photo for door 1")).to_have_count(0)
    sign_in(phone)
    expect(phone.get_by_role("img", name="Photo for door 1")).to_be_visible()
