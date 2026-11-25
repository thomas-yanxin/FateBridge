"""Register, seal, and evaluate Jyotish study commitments from separate files."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

if __name__ == "__main__" and not __package__:
    # note (entrypoint): Direct execution must resolve the checkout-only validation package.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
else:
    pass

from validation.jyotish_study_binding import (
    JyotishProtocol,
    blind_outcome_sheet,
    register,
    reveal_and_evaluate,
    seal_forecasts,
)
from validation.predictions import Forecast, Outcome


def read_json_file(path: str) -> JsonValue:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_commitment(path: str) -> dict[str, JsonValue]:
    commitment = read_json_file(path)
    if not isinstance(commitment, dict):
        raise ValueError("A study commitment must be a JSON mapping")
    else:
        return commitment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("--protocol", required=True)
    reg.add_argument("--model", required=True)
    reg.add_argument(
        "--artifact",
        action="append",
        required=True,
        metavar="NAME=PATH",
        help="Repeat for every protocol artifact; hash actual file bytes before registration",
    )
    seal = sub.add_parser("seal")
    seal.add_argument("--registration", required=True)
    seal.add_argument("--forecasts", required=True)
    seal.add_argument("--evidence", action="append", required=True, metavar="CASE=PATH")
    sheet = sub.add_parser("blind-sheet")
    sheet.add_argument("--registration", required=True)
    score = sub.add_parser("evaluate")
    score.add_argument("--registration", required=True)
    score.add_argument("--sealed", required=True)
    score.add_argument("--outcomes", required=True)
    score.add_argument(
        "--outcome-source", action="append", default=[], metavar="CASE=PATH"
    )
    for command in (reg, seal, sheet, score):
        command.add_argument("--output", required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)

    def read_bound_files(file_arguments: list[str]) -> dict[str, bytes]:
        bindings: dict[str, bytes] = {}
        for file_argument in file_arguments:
            if "=" not in file_argument:
                parser.error("file bindings must use NAME=PATH")
            else:
                pass
            name, path = file_argument.split("=", 1)
            if not name or name in bindings:
                parser.error("empty or duplicate file binding")
            else:
                pass
            bindings[name] = Path(path).read_bytes()
        return bindings

    if args.action == "register":
        result = register(
            JyotishProtocol.model_validate(read_json_file(args.protocol)),
            Path(args.model).read_bytes(),
            at=now,
            artifacts=read_bound_files(args.artifact),
        )
    elif args.action == "seal":
        result = seal_forecasts(
            read_commitment(args.registration),
            TypeAdapter(list[Forecast]).validate_python(read_json_file(args.forecasts)),
            at=now,
            evidence=read_bound_files(args.evidence),
        )
    elif args.action == "blind-sheet":
        result = blind_outcome_sheet(read_commitment(args.registration))
    else:
        result = reveal_and_evaluate(
            read_commitment(args.registration),
            read_commitment(args.sealed),
            TypeAdapter(list[Outcome]).validate_python(read_json_file(args.outcomes)),
            at=now,
            outcome_sources=read_bound_files(args.outcome_source),
        )
    # note (study): Keep each confirmed packet available for independent timestamps.
    with Path(args.output).open("x", encoding="utf-8") as output:
        output.write(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
    print(
        json.dumps(
            {
                "action": args.action,
                "output": args.output,
                "authority_certified": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
else:
    pass
