"""Publish frozen same-edition current-void-fill control qualification."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/liuyao_void_control_v31"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-void-control-v31.json"


def build() -> dict[str, Any]:
    for name, digest in json.loads(
        (REFERENCE / "freeze.json").read_text(encoding="utf-8")
    )["sha256"].items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen current-void control reference changed: {name}")
    profile = json.loads((REFERENCE / "profile.json").read_text(encoding="utf-8"))
    source = (REFERENCE / profile["source"]["file"]).resolve()
    if not source.is_relative_to((ROOT / "tests/fixtures").resolve()):
        raise ValueError("Current-void control source escaped fixtures")
    if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError("Original current-void control scan changed")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit("Current-void control profile is stale")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
    print("Current-void control clauses and original scan verified")


if __name__ == "__main__":
    main()
