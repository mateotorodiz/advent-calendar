from collections import Counter
import json
from pathlib import Path, PureWindowsPath
import shutil
from tempfile import TemporaryDirectory
from typing import Self

from pydantic import (
    BaseModel, ConfigDict, HttpUrl, StrictInt, TypeAdapter, ValidationError,
    field_validator, model_validator,
)


MEDIA_FORMATS = {"photo": {".jpg", ".jpeg", ".png", ".webp"}, "audio": {".mp3", ".m4a", ".wav"}}
MAX_MEDIA_BYTES = 10 * 1024 * 1024
DAY_COUNTS = {"demo": 6, "production": 24}


class PackageError(ValueError):
    pass


class Gift(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    day: StrictInt
    note: str | None = None
    joke: str | None = None
    song: HttpUrl | None = None
    photo: str | None = None
    audio: str | None = None

    @field_validator("song")
    @classmethod
    def require_public_song_link(cls, song: HttpUrl | None) -> HttpUrl | None:
        if song and (song.scheme != "https" or song.username or song.password):
            raise ValueError("use an HTTPS song link without login credentials")
        return song

    @model_validator(mode="after")
    def require_content(self) -> Self:
        if not any((self.note, self.joke, self.song, self.photo, self.audio)):
            raise ValueError("add at least one note, joke, song, photo, or audio file")
        return self


def load_gifts(content: Path, count: int) -> list[Gift]:
    try:
        gifts = TypeAdapter(list[Gift]).validate_json((content / "gifts.json").read_bytes())
    except ValidationError as error:
        messages = []
        for issue in error.errors(include_input=False):
            location = "".join(f"[{part + 1}]" if isinstance(part, int) else f".{part}" for part in issue["loc"])
            messages.append(f"gifts.json{location}: {issue['msg']}")
        raise PackageError("\n".join(messages)) from None

    days = Counter(gift.day for gift in gifts)
    expected = set(range(1, count + 1))
    errors = []
    for label, numbers in (
        ("missing days", expected - days.keys()),
        ("duplicate days", {day for day, occurrences in days.items() if occurrences > 1}),
        ("unexpected days", days.keys() - expected),
    ):
        if numbers:
            errors.append(f"{label}: {', '.join(map(str, sorted(numbers)))}")
    if errors:
        raise PackageError("; ".join(errors))
    return sorted(gifts, key=lambda gift: gift.day)


def media_path(content: Path, value: str, day: int, kind: str) -> Path:
    label = f"day {day} {kind}"
    relative = PureWindowsPath(value)
    if relative.anchor or ".." in relative.parts or ":" in value:
        raise PackageError(f"{label}: use a relative path inside the content folder")
    candidate = content.joinpath(*relative.parts).resolve()
    if not candidate.is_relative_to(content):
        raise PackageError(f"{label}: file must stay inside the content folder")
    if candidate.suffix.lower() not in MEDIA_FORMATS[kind]:
        raise PackageError(f"{label}: unsupported format, use {', '.join(sorted(MEDIA_FORMATS[kind]))}")
    if not candidate.is_file():
        raise PackageError(f"{label}: path must point to a regular file")
    if not 0 < candidate.stat().st_size <= MAX_MEDIA_BYTES:
        raise PackageError(f"{label}: file must be nonempty and at most 10 MiB")
    return candidate


def package_gifts(mode: str, project: Path) -> Path:
    project = project.resolve()
    content = (Path(__file__).with_name("demo") if mode == "demo" else project / "content").resolve()
    gifts = load_gifts(content, DAY_COUNTS[mode])
    manifest = {}
    files = {}
    for gift in gifts:
        entry = gift.model_dump(mode="json", include={"note", "joke", "song"}, exclude_none=True)
        for kind in MEDIA_FORMATS:
            value = getattr(gift, kind)
            if value:
                source = media_path(content, value, gift.day, kind)
                name = f"{kind}{source.suffix.lower()}"
                entry[kind] = name
                files[Path(str(gift.day), name)] = source
        manifest[str(gift.day)] = {key: value for key, value in entry.items() if value}

    dist = project / "dist"
    output = dist / mode / "_gifts"
    if output.resolve() != output:
        raise PackageError("bundle output must stay under dist without redirected directories")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = dist / f".{mode}.build-lock"
    try:
        with lock.open("x", encoding="utf-8"):
            pass
    except FileExistsError:
        raise PackageError(f"a {mode} build is already in progress ({lock})") from None

    try:
        with TemporaryDirectory(prefix=f".{mode}-", dir=dist) as temporary:
            staged = Path(temporary) / "bundle"
            staged.mkdir()
            for relative, source in files.items():
                destination = staged / relative
                destination.parent.mkdir(exist_ok=True)
                shutil.copyfile(source, destination)
            (staged / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )

            previous = Path(temporary) / "previous"
            if output.exists():
                output.rename(previous)
            try:
                staged.rename(output)
            except OSError:
                if previous.exists():
                    previous.rename(output)
                raise
    finally:
        lock.unlink()
    return output
