"""Replay the named Gujin 43 elapsed-318 four-cardinal example."""

import argparse
import json

from fatebridge.core.guolao_cardinals import gujin43_cardinal_example


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", required=True, choices=["gujin43-318"])
    parser.add_argument("--profile", required=True, choices=["nlc166", "wikisource"])
    args = parser.parse_args()
    result = gujin43_cardinal_example(profile=args.profile)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
