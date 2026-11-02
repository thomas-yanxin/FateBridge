"""Audit the full frozen24-term protocol; retain every failed or degraded row."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.fengshui_solar_terms import (
    audit_solar_terms_reference,
    load_solar_terms_reference,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-folder",
        type=Path,
        default=Path(__file__).parents[1] / "tests/fixtures/fengshui_all_terms_v1",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Keep the previous audit; choose a new output file")
    reference = load_solar_terms_reference(args.reference_folder)
    report = audit_solar_terms_reference(
        reference, progress=lambda n: print(f"Audited {n}/10104", flush=True)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "comparisons"}))
    return 0 if report["all_scoped_tt_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
