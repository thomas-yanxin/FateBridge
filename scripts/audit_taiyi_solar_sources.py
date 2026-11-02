"""Reproduce pinned official-minute and Taiyi boundary source comparisons."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.taiyi_solar_sources import audit

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(ROOT / "tests/fixtures/taiyi_jinjing_v30")
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "scoped_controls_passed": report["scoped_controls_passed"],
                "whole_calendar_acceptance_passed": False,
            }
        )
    )
    # Full calendar/classical acceptance is still open, even if these pass.
    raise SystemExit(1)
