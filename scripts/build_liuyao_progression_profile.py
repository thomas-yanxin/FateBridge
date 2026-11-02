"""Publish the frozen original-scan progression clauses without changing them."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/liuyao_progression_v8"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-progression-v8.json"


def build() -> dict[str, Any]:
    frozen = json.loads((REFERENCE / "freeze.json").read_text(encoding="utf-8"))
    for name, digest in frozen["sha256"].items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen progression reference changed: {name}")
    profile: dict[str, Any] = json.loads(
        (REFERENCE / "profile.json").read_text(encoding="utf-8")
    )
    source = (REFERENCE / profile["source"]["file"]).resolve()
    if not source.is_relative_to((ROOT / "tests/fixtures").resolve()):
        raise ValueError("Progression source escaped fixture directory")
    if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError("Original progression scan changed")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Progression profile is stale")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
    print("Progression clauses, scan and pre-implementation cases verified")


if __name__ == "__main__":
    main()
