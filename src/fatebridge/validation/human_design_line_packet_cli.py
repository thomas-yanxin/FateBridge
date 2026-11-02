"""Build/verify complete-run line packets from local JSON or JSON.gz files."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from fatebridge.core.human_design_line_catalogue import _nonfinite, _object
from fatebridge.services.human_design_line_reading import (
    LineReadingInputError,
    build_human_design_line_packet,
)
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.human_design_line_reading import (
    verify_human_design_line_packet,
)


def read(path: Path) -> dict:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    value = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
    if not isinstance(value, dict):
        raise ValueError("A complete JSON object is required")
    return value


def write(path: Path, value: dict) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    if path.suffix == ".gz":
        raw = gzip.compress(raw, mtime=0)
    with path.open("xb") as stream:
        stream.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("source_result", type=Path)
    build.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("source_result", type=Path)
    verify.add_argument("packet", type=Path)
    verify.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        source = read(args.source_result)
        if args.command == "build":
            packet = build_human_design_line_packet(source)
            write(args.output, packet)
            print(
                json.dumps(
                    {
                        "status": "built_calculation_bound_reference_packet",
                        "source_identity": packet["source_identity"],
                        "coverage": packet["line_reading"]["coverage"],
                        "complete384_line_semantics_accepted": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        receipt = verify_human_design_line_packet(read(args.packet), source)
        if args.output is not None:
            write(args.output, receipt)
        print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
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
