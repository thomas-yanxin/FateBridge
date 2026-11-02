"""Offline source-admission audit. Exit 2 means retained source findings.

--check compares the saved report and still exits 2 for a rejected source;
reproducing a failure is not source acceptance. No runtime data are generated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fatebridge.validation.sukuyo_calendar_sources import audit_candidate

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture", type=Path, default=ROOT / "tests/fixtures/sukuyo_hutime_v1"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = audit_candidate(args.fixture)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.check:
        if args.output.read_text() != rendered:
            raise SystemExit("Candidate audit report drift")
    else:
        args.output.write_text(rendered)
    print(
        json.dumps(
            {
                "structural_import_eligible": report["structural_import_eligible"],
                "blocking_findings": report["blocking_findings"],
            }
        )
    )
    if report["blocking_findings"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
