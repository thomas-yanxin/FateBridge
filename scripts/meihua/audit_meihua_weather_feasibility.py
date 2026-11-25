"""Check a committed forecast vector before spending a cohort on its score."""

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

from validation.meihua_weather_feasibility import audit_feasibility_vector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vector", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_feasibility_vector(args.vector, expected_sha256=args.expected_sha256)
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    # Successful verification need not mean the proposed model can pass.


if __name__ == "__main__":
    main()
else:
    pass
