"""Package the corrected independent reading, without rewriting its first report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "tests/data/ziwei_independent/independent_readings_r22_v1"
TARGET = ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-days-review-r22.json"


def build() -> dict:
    manifest = json.loads((FROZEN / "manifest.json").read_text())
    wanted = {row["path"]: row["sha256"] for row in manifest["files"]}
    paths = ["reports/day-review.json", "reports/day-review-errata-01.json"]
    for relative in paths:
        if (
            hashlib.sha256((FROZEN / relative).read_bytes()).hexdigest()
            != wanted[relative]
        ):
            raise ValueError("Independent reading checksum mismatch: " + relative)
    first = json.loads((FROZEN / paths[0]).read_text())
    erratum = json.loads((FROZEN / paths[1]).read_text())
    if erratum["frozen_original"]["sha256"] != wanted[paths[0]]:
        raise ValueError("Erratum does not identify the retained first report")
    rows = {(r["bureau"], r["day"]): r for r in first["day_to_branch_rows"]}
    expected = {(b, d) for b in range(2, 7) for d in range(1, 31)}
    if len(first["day_to_branch_rows"]) != 150 or set(rows) != expected:
        raise ValueError("Independent reading denominator changed")
    correction = erratum["corrected_day_to_branch_row"]
    rows[(correction["bureau"], correction["day"])] = correction
    return {
        "id": "naj_ming_day_independent_review_r22_corrected_v1",
        "source_report_sha256": wanted[paths[0]],
        "erratum_sha256": wanted[paths[1]],
        "frozen_manifest_sha256": hashlib.sha256(
            (FROZEN / "manifest.json").read_bytes()
        ).hexdigest(),
        "source_report": "tests/data/ziwei_independent/independent_readings_r22_v1/reports/day-review.json",
        "separate_erratum": "tests/data/ziwei_independent/independent_readings_r22_v1/reports/day-review-errata-01.json",
        "new_edition": False,
        "external_human_experts": 0,
        "records": [rows[key] for key in sorted(rows)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != text:
            raise SystemExit("Ziwei independent-reading disclosure is stale")
    else:
        TARGET.write_text(text)


if __name__ == "__main__":
    main()
