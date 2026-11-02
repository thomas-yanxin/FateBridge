"""Copy the fully frozen public source-condition plan; never infer a label."""

import argparse
import hashlib
from pathlib import Path

from fatebridge.core.source_conditions import DATA_NAME, PLAN_SHA256

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = (
        ROOT
        / "tests/fixtures/bazi_source_conditions_public_v1/publication-plan-first.json"
    )
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise SystemExit("Frozen source-condition plan hash changed")
    target = ROOT / "src/fatebridge/data/reference" / DATA_NAME
    if args.check:
        if not target.exists() or target.read_bytes() != raw:
            raise SystemExit("Packaged source-condition layer drifted")
    else:
        target.write_bytes(raw)
    print(
        "19 source-condition reviews / 21 existing records; no label or calculation change"
    )
