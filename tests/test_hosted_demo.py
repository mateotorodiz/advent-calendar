from datetime import datetime, timezone
import json
from pathlib import Path

import httpx
import pytest


def test_hosted_config_uses_only_demo_assets_and_requires_secrets():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "wrangler.demo.jsonc").read_text(encoding="utf-8"))
    assert config["name"] == "advent-calendar-demo"
    assert config["main"] == "src/worker/index.ts"
    assert config["assets"] == {
        "directory": "dist/demo", "binding": "ASSETS", "run_worker_first": True,
    }
    assert config["vars"] == {"CALENDAR_SCHEDULE": "demo"}
    assert set(config["secrets"]["required"]) == {"CALENDAR_PASSPHRASE", "SESSION_SIGNING_KEY"}


@pytest.mark.parametrize("opened", [0, 1, 2, 3])
def test_demo_smoke_check(browser_worker_url, opened):
    from advent_tools.demo_check import check_demo

    now = datetime(2026, 11, 27 + opened, 20, tzinfo=timezone.utc)
    headers = {"x-fixture-time": now.isoformat(), "x-fixture-client": f"hosted-smoke-{opened}"}
    with httpx.Client(base_url=browser_worker_url, headers=headers, verify=False, trust_env=False) as client:
        assert check_demo(client, "fixture-passphrase", now=now) == opened
