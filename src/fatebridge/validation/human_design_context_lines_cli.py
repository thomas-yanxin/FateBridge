"""Build/verify all retained context line packets from complete local JSON runs."""

import argparse
import json
from pathlib import Path

from fatebridge.services.human_design_context_lines import (
    build_human_design_context_packet,
)
from fatebridge.services.human_design_line_reading import LineReadingInputError
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.human_design_context_lines import (
    verify_human_design_context_packet,
)
from fatebridge.validation.human_design_line_packet_cli import read, write


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("source_result", type=Path)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument(
        "--reference-category",
        choices=["lines", "lines_v3", "lines_v4", "lines_v5", "lines_v6", "lines_v7"],
        default="lines",
    )
    verify = commands.add_parser("verify")
    verify.add_argument("source_result", type=Path)
    verify.add_argument("packet", type=Path)
    verify.add_argument("--output", type=Path)
    verify.add_argument(
        "--reference-category",
        choices=["lines", "lines_v3", "lines_v4", "lines_v5", "lines_v6", "lines_v7"],
        default="lines",
    )
    args = parser.parse_args()
    try:
        source = read(args.source_result)
        if args.command == "build":
            packet = build_human_design_context_packet(
                source, reference_category=args.reference_category
            )
            write(args.output, packet)
            print(
                json.dumps(
                    {
                        "status": "built_original_bound_context_line_packet",
                        "coverage": packet["coverage"],
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        receipt = verify_human_design_context_packet(
            read(args.packet), source, reference_category=args.reference_category
        )
        if args.output is not None:
            write(args.output, receipt)
        print(json.dumps(receipt, ensure_ascii=False))
        return int(receipt["status"] == "rejected")
    except LineReadingInputError as exc:
        error = {
            "status": "rejected",
            "error": "original_run_not_verified",
            "verification": exc.verification,
        }
    except EphemerisSourceError as exc:
        error = {"status": "rejected", "error": exc.reason}
    except (ValueError, OSError, EOFError, TypeError) as exc:
        error = {"status": "rejected", "error": type(exc).__name__, "message": str(exc)}
    print(json.dumps(error, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
