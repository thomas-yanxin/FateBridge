"""Official calendar-standard source reading; no saved production replay."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_calendar_standard_v1"
PIN = "3f39e6854075f034c3396bf41b33f392720eb821a60a241258eba86369e35890"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_reading(folder: Path = CORPUS) -> dict[str, object]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Official reading identity changed")
    files = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(files) | {"freeze.json"}:
        raise ValueError("Official reading inventory changed")
    if any(sha(folder / n) != h for n, h in files.items()):
        raise ValueError("Official reading content changed")
    reading: dict[str, object] = json.loads((folder / "reading.json").read_text())
    return reading
