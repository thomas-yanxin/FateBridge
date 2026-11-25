"""Audit all4824supported solar crossings against a committed TT reference."""

import sys as _sys
from pathlib import Path as _Path

_VAL_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_VAL_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_VAL_REPO_ROOT))
else:
    pass


import argparse
import json
from pathlib import Path

from validation.meihua_solar_seconds import audit_solar_seconds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_solar_seconds(args.reference, expected_sha256=args.expected_sha256)
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report["TT_reference_gate_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
