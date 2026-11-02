"""Check a committed forecast vector before spending a cohort on its score."""

import argparse
import json
from pathlib import Path

from fatebridge.validation.meihua_weather_feasibility import audit_feasibility_vector


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
