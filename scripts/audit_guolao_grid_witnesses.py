"""Compare one explicitly selected, collated grid location across named scans."""

import argparse
import json

from fatebridge.core.guolao_grid_witnesses import compare_witnesses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palace", required=True)
    parser.add_argument("--column", required=True, type=int)
    args = parser.parse_args()
    try:
        result = compare_witnesses(palace=args.palace, column=args.column)
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
