"""Check bounded named-author IHDS examples without declaring full acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fatebridge.validation.human_design_primary_fixing import primary_fixing_checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-acceptance", action="store_true")
    args = parser.parse_args()
    result = primary_fixing_checks(Path(__file__).resolve().parents[1])
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return int(
        result["status"] == "failed"
        or args.require_full_acceptance
        and not result["full_384_line_meaning_acceptance"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
