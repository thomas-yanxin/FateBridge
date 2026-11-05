"""Named three-shadow interpolation and original clock-bin audit."""

from __future__ import annotations

import argparse
import json

from fatebridge.core.guolao_gnomon_epoch import (
    CLOCK_POLICY,
    PROFILES,
    SEASONS,
    load_gnomon_epoch,
    source_clock_bin,
)
from fatebridge.validation.guolao_gnomon_epoch import audit_gnomon_epoch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit")
    for name in ("triad", "mean"):
        p = sub.add_parser(name)
        p.add_argument("--profile", choices=PROFILES, required=True)
        p.add_argument("--season", choices=SEASONS, required=True)
        if name == "triad":
            p.add_argument("--case-id", type=int, required=True)
    clock = sub.add_parser("clock-bin")
    clock.add_argument("--clock-policy", choices=[CLOCK_POLICY], required=True)
    clock.add_argument("--branch", required=True)
    clock.add_argument("--half", choices=["初", "正"], required=True)
    clock.add_argument("--ke", type=int, required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            result = audit_gnomon_epoch()
        elif args.command == "clock-bin":
            result = source_clock_bin(
                args.branch, args.half, args.ke, clock_policy=args.clock_policy
            )
        else:
            model = load_gnomon_epoch(args.profile)
            result = (
                model.triad(args.season, args.case_id)
                if args.command == "triad"
                else model.season_mean(args.season)
            )
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
