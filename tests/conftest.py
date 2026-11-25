import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

import httpx
import pytest

from advent_tools.gifts import package_gifts


@pytest.fixture(scope="session")
def worker_url(tmp_path_factory):
    yield from run_worker(tmp_path_factory)


@pytest.fixture(scope="session")
def release_worker_url(tmp_path_factory):
    yield from run_worker(tmp_path_factory, use_release_entry=True)


@pytest.fixture(scope="session")
def packaged_demo_worker_url(tmp_path_factory):
    project = tmp_path_factory.mktemp("demo-project")
    bundle = package_gifts("demo", project)
    yield from run_worker(tmp_path_factory, assets_directory=bundle.parent)


@pytest.fixture(scope="session")
def browser_worker_url(tmp_path_factory):
    project = Path(__file__).resolve().parents[1]
    scratch = tmp_path_factory.mktemp("web-project")
    bundle = package_gifts("demo", scratch)
    subprocess.run(["node", str(project / "src" / "web" / "build.mjs"), "demo"],
                   cwd=scratch, check=True)
    yield from run_worker(tmp_path_factory, assets_directory=bundle.parent, https=True)


def run_worker(tmp_path_factory, *, use_release_entry=False, assets_directory=None, https=False):
    project = Path(__file__).resolve().parents[1]
    wrangler = project / "node_modules" / "wrangler" / "bin" / "wrangler.js"
    config = project / "tests" / "fixtures" / "wrangler.jsonc"
    if not wrangler.is_file():
        pytest.fail("Wrangler is missing. Run pnpm install --frozen-lockfile first.")

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    scratch = tmp_path_factory.mktemp("wrangler")
    if assets_directory is not None:
        settings = json.loads(config.read_text(encoding="utf-8"))
        settings["main"] = (config.parent / settings["main"]).as_posix()
        settings["assets"]["directory"] = assets_directory.as_posix()
        config = scratch / "wrangler.jsonc"
        config.write_text(json.dumps(settings), encoding="utf-8")
    log_path = scratch / "wrangler.log"
    use_https = https or use_release_entry
    protocol = "https" if use_https else "http"
    url = f"{protocol}://127.0.0.1:{port}"
    entry_args = []
    if use_release_entry:
        entry_args = [
            str(project / "src" / "worker" / "index.ts"),
            "--var", "CALENDAR_SCHEDULE:production",
        ]
    with log_path.open("wb") as log:
        worker = subprocess.Popen(
            [
                "node", str(wrangler), "dev", *entry_args, "--local",
                "--config", str(config), "--ip", "127.0.0.1",
                "--local-protocol", protocol,
                "--port", str(port), "--inspector-port", "0",
                "--persist-to", str(scratch / "state"),
            ],
            cwd=project,
            env={
                **os.environ,
                "CI": "true",
                "XDG_CONFIG_HOME": str(scratch / "config"),
                "WRANGLER_SEND_METRICS": "false",
                "CLOUDFLARE_CF_FETCH_ENABLED": "false",
            },
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
        try:
            deadline = time.monotonic() + 30
            # HTTPS fixtures use Wrangler's self-signed loopback certificate.
            with httpx.Client(trust_env=False, timeout=0.5, verify=not use_https) as client:
                while worker.poll() is None and time.monotonic() < deadline:
                    try:
                        client.get(f"{url}/healthz")
                    except httpx.TransportError:
                        time.sleep(0.1)
                    else:
                        break
                else:
                    output = log_path.read_text(encoding="utf-8", errors="replace")
                    pytest.fail(f"Local Wrangler failed to start.\n{output}")
            yield url
        finally:
            # Wrangler starts workerd as a child. Stop the entire process tree.
            if os.name == "nt":
                if worker.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(worker.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
            else:
                try:
                    os.killpg(worker.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
