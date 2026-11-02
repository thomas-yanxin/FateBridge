"""Publish the source frozen before the day-value/month-break implementation."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/liuyao_month_break_v24"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-month-break-v24.json"


def build() -> dict[str, Any]:
    for freeze in ("freeze-r1.json", "quote-freeze.json"):
        frozen = json.loads((REFERENCE / freeze).read_text())
        for name, digest in frozen["sha256"].items():
            if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Frozen month-break reference changed: {name}")
    profile: dict[str, Any] = json.loads((REFERENCE / "profile-r2.json").read_text())
    source = (REFERENCE / profile["source"]["file"]).resolve()
    if not source.is_relative_to((ROOT / "tests/fixtures").resolve()):
        raise ValueError("Month-break source escaped fixture directory")
    if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError("Month-break source scan changed")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text() != rendered:
            raise SystemExit("Month-break source profile is stale")
    else:
        OUTPUT.write_text(rendered)
    print("Pre-implementation month-break sources and cases verified")


if __name__ == "__main__":
    main()
