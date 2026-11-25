from importlib.metadata import version

import httpx

import advent_tools


def test_tooling_package_is_installed():
    assert advent_tools.__package__ == "advent_tools"
    assert version("advent-calendar") == "0.1.0"


def test_worker_answers_with_json(worker_url):
    response = httpx.get(f"{worker_url}/healthz", timeout=5, trust_env=False)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_worker_can_serve_a_dummy_asset(worker_url):
    response = httpx.get(f"{worker_url}/dummy.txt", timeout=5, trust_env=False)

    assert response.status_code == 200
    assert response.text.strip() == "Advent Calendar test fixture"
