"""Generate source identity corrections; retain v7 and every original claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fatebridge.core.source_identity import (
    PARENT_SHA256,
    PLAN_SHA256,
    build_identity_index,
)
from scripts.historical_source_identity import HistoricalSources

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path("src/fatebridge/data/reference")
PLAN = Path("tests/fixtures/bazi_source_identity_v1/patch-plan-first.json")


def generate() -> dict[str, Any]:
    parent = (ROOT / REFERENCE / "bazi-source-annotations-v7.json").read_bytes()
    plan = (ROOT / PLAN).read_bytes()
    if (
        hashlib.sha256(parent).hexdigest() != PARENT_SHA256
        or hashlib.sha256(plan).hexdigest() != PLAN_SHA256
    ):
        raise ValueError("Source identity protocol or parent index changed")
    # Reproduce the sealed v8 edition. Its generator identity denotes the
    # original edition, while the CLI reports the actual maintenance runner.
    original_generator = (
        "0019c19fd25468cc3709f00d9b9c581b33d8aa4ebed23a187893d7b28dc198fd"
    )
    if not HistoricalSources(ROOT).matches(
        ROOT / "scripts/build_bazi_source_index_v8.py", original_generator
    ):
        raise ValueError("Original v8 generator source changed")
    return build_identity_index(
        json.loads(parent), json.loads(plan), original_generator
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(generate(), ensure_ascii=False, indent=2) + "\n").encode()
    artifacts = {
        ROOT / REFERENCE / "bazi-source-annotations-v8.json": raw,
        ROOT
        / REFERENCE
        / "bazi-source-witness-identity-v1.json": (ROOT / PLAN).read_bytes(),
    }
    for path, value in artifacts.items():
        if args.check or path.exists():
            if path.read_bytes() != value:
                raise ValueError(
                    "Preserve generated first identity artifact: " + str(path)
                )
        else:
            path.open("xb").write(value)
    print(
        json.dumps(
            {
                "records": 367,
                "publisher_corrections": 58,
                "printed_names": 2,
                "strength_regrades": 0,
                "maintenance_runner_sha256": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
