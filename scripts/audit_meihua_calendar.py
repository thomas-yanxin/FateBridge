"""Compare the complete supported civil-date cohort with TAM and HKO tables."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_calendar import audit_supported_calendar


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tam-references",
        type=Path,
        default=root / "tests/fixtures/meihua_calendar_v2",
    )
    parser.add_argument(
        "--hko-references", type=Path, default=root / "tests/fixtures/meihua_v1"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_supported_calendar(args.tam_references, args.hko_references)
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    return 0 if report["selected_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
