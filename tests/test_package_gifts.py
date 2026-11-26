import json
import os
import subprocess
import sys

import pytest


def package(directory, mode="production"):
    return subprocess.run(
        [sys.executable, "-m", "advent_tools", mode], cwd=directory,
        capture_output=True, text=True, encoding="utf-8", check=False,
    )


def write_gifts(directory, gifts):
    content = directory / "content"
    content.mkdir(exist_ok=True)
    (content / "gifts.json").write_text(json.dumps(gifts), encoding="utf-8")
    return content


@pytest.fixture
def gifts():
    return [{"day": day, "note": f"Gift {day}"} for day in range(1, 25)]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"day": 2}, "duplicate days: 2"),
        ({"day": 25}, "missing days: 1"),
        ({"note": "  "}, "add at least one"),
        ({"song": "not-a-url"}, "song"),
        ({"song": "http://example.com"}, "HTTPS"),
        ({"photo": "missing.jpg"}, "regular file"),
        ({"audio": "../outside.wav"}, "inside the content folder"),
        ({"photo": "C:\\outside.jpg"}, "inside the content folder"),
        ({"photo": "data.svg"}, "format"),
        ({"day": "1"}, "integer"),
    ],
)
def test_invalid_gifts_fail_before_creating_a_bundle(tmp_path, gifts, change, message):
    gifts[0].update(change)
    write_gifts(tmp_path, gifts)

    result = package(tmp_path)

    assert result.returncode == 2
    assert message in result.stderr
    assert not (tmp_path / "dist").exists()


def test_missing_days_are_rejected(tmp_path, gifts):
    write_gifts(tmp_path, gifts[:-1])
    result = package(tmp_path)
    assert result.returncode == 2
    assert "missing days: 24" in result.stderr


def test_command_packages_named_media_and_replaces_previous_bundle(tmp_path, gifts):
    gifts[0].update({"photo": "media/name with spaces.JPG", "song": "https://example.com/song"})
    content = write_gifts(tmp_path, gifts)
    (content / "media").mkdir()
    (content / "media" / "name with spaces.JPG").write_bytes(b"fixture photo data")
    output = tmp_path / "dist" / "production" / "_gifts"
    unrelated = output.parent / "site.txt"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("Website assets", encoding="utf-8")

    result = package(tmp_path)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {str(day) for day in range(1, 25)}
    assert manifest["1"] == {
        "note": "Gift 1", "photo": "photo.jpg", "song": "https://example.com/song",
    }
    assert (output / "1" / "photo.jpg").read_bytes() == b"fixture photo data"

    (content / "media" / "name with spaces.JPG").unlink()
    assert package(tmp_path).returncode == 2
    assert (output / "1" / "photo.jpg").is_file()

    del gifts[0]["photo"]
    write_gifts(tmp_path, gifts)
    assert package(tmp_path).returncode == 0
    assert not (output / "1" / "photo.jpg").exists()
    assert unrelated.read_text(encoding="utf-8") == "Website assets"


def test_symlinked_media_outside_content_is_rejected(tmp_path, gifts):
    gifts[0]["audio"] = "linked/voice.wav"
    content = write_gifts(tmp_path, gifts)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "voice.wav").write_bytes(b"placeholder")
    link = content / "linked"
    if os.name == "nt":
        # Directory junctions exercise the same resolved-path check without symlink privileges.
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "$ErrorActionPreference = 'Stop'\n"
             "New-Item -ItemType Junction -Path $env:ADVENT_TEST_LINK -Target $env:ADVENT_TEST_TARGET | Out-Null"],
            env={**os.environ, "ADVENT_TEST_LINK": str(link), "ADVENT_TEST_TARGET": str(outside)},
            capture_output=True, check=True,
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    result = package(tmp_path)
    assert result.returncode == 2
    assert "inside the content folder" in result.stderr


def test_oversized_media_is_rejected(tmp_path, gifts):
    gifts[0]["audio"] = "voice.wav"
    content = write_gifts(tmp_path, gifts)
    with (content / "voice.wav").open("wb") as file:
        file.truncate(10 * 1024 * 1024 + 1)
    result = package(tmp_path)
    assert result.returncode == 2
    assert "at most 10 MiB" in result.stderr


def test_demo_build_only_packages_committed_dummy_gifts(tmp_path, gifts):
    gifts[0]["note"] = "Private production content"
    write_gifts(tmp_path, gifts)
    result = package(tmp_path, "demo")
    assert result.returncode == 0, result.stderr
    output = tmp_path / "dist" / "demo" / "_gifts"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {str(day) for day in range(1, 7)}
    assert "Private production content" not in str(manifest)
    assert (output / "1" / "photo.png").is_file()
    assert (output / "2" / "audio.wav").is_file()
    assert not (tmp_path / "dist" / "production").exists()
