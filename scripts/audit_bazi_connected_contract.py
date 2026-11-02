"""Compare an observed MCP output contract with complete frozen public results."""

from __future__ import annotations

import argparse
import gzip
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def contract_record(document: Any) -> dict[str, Any]:
    if isinstance(document, str):
        document = json.loads(document)
    if "contents" in document:
        if document.get("server") != "fatebridge" or document.get("uri") != (
            "fatebridge://tools/bazi_source_compare"
        ):
            raise ValueError("Observed contract names a different server or tool")
        if len(document["contents"]) != 1:
            raise ValueError("Expected one complete observed contract resource")
        document = json.loads(document["contents"][0]["text"])
    if document.get("matched_count") != 1 or document.get("detail") != "full":
        raise ValueError("Expected a complete single-tool contract")
    records = document["tools"]
    if len(records) != 1 or records[0].get("tool") != "bazi_source_compare":
        raise ValueError("Observed contract names a different tool")
    return records[0]


def errors(validator: Draft202012Validator, value: Any) -> list[dict[str, Any]]:
    def leaves(error):
        if error.context:
            return [leaf for child in error.context for leaf in leaves(child)]
        return [
            {
                "path": list(error.absolute_path),
                "schema_path": list(error.absolute_schema_path),
                "validator": error.validator,
                "expected": error.validator_value,
            }
        ]

    return [
        {
            "path": list(e.absolute_path),
            "schema_path": list(e.absolute_schema_path),
            "validator": e.validator,
            "message": e.message,
            "context": [c.message for c in e.context],
            "leaf_errors": leaves(e),
        }
        for e in sorted(
            validator.iter_errors(value), key=lambda e: str(e.absolute_path)
        )
    ]


def compare(
    observed: Any, expected: dict[str, Any], current_schema: dict[str, Any]
) -> dict[str, Any]:
    record = contract_record(observed)
    for schema in (record["input_schema"], record["output_schema"], current_schema):
        Draft202012Validator.check_schema(schema)
    inbound = Draft202012Validator(record["input_schema"])
    old_output = Draft202012Validator(record["output_schema"])
    fresh_output = Draft202012Validator(current_schema)
    cases = expected["cases"]
    if not cases or len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("Frozen case population is empty or contains repeated IDs")
    rows = []
    for case in cases:
        pillars = case["pillars"]
        if len(pillars) != 4:
            raise ValueError("Every frozen case must retain all four supplied pillars")
        values = dict(
            zip(("year_pillar", "month_pillar", "day_pillar", "hour_pillar"), pillars)
        )
        rows.append(
            {
                "case_id": case["case_id"],
                "pillars": pillars,
                "computed_strength": case["result"]["current_calculation"][
                    "strength_level"
                ],
                "source_comparison_status": case["result"]["source_comparison"][
                    "status"
                ],
                "declared_input_errors": errors(inbound, values),
                "connected_declared_output_errors": errors(old_output, case["result"]),
                "current_output_errors": errors(fresh_output, case["result"]),
                "result_sha256": sha256(
                    json.dumps(
                        case["result"],
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode()
                ).hexdigest(),
            }
        )
    return {
        "scope": "Declared-contract comparison against every supplied frozen result, not a new calculation, live code inspection, service exception trace or prediction evaluation.",
        "case_count": len(rows),
        "cases": rows,
        "declared_input_rejected_cases": sum(
            bool(r["declared_input_errors"]) for r in rows
        ),
        "connected_declared_output_rejected_cases": sum(
            bool(r["connected_declared_output_errors"]) for r in rows
        ),
        "current_output_rejected_cases": sum(
            bool(r["current_output_errors"]) for r in rows
        ),
        "declared_contract_compatible": not any(
            r["declared_input_errors"]
            or r["connected_declared_output_errors"]
            or r["current_output_errors"]
            for r in rows
        ),
        "connected_service_exception_cause_conclusively_observed": False,
        "connected_deployment_accepted": False,
        "new_model_invocations": 0,
        "source_labels_or_calculations_changed": False,
        "original_gates_superseded": False,
        "full_goal_complete": False,
        "authority_certified": False,
        "overall_score": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connected-contract", type=Path, required=True)
    parser.add_argument("--expected-results", type=Path, required=True)
    parser.add_argument("--current-schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-compatible", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve earlier diagnosis; choose a new output path")
    paths = [args.connected_contract, args.expected_results, args.current_schema]
    before = {str(p): sha256(p.read_bytes()).hexdigest() for p in paths}
    schema = read(args.current_schema)
    result = compare(
        read(args.connected_contract),
        read(args.expected_results),
        schema["output_schema"],
    )
    after = {str(p): sha256(p.read_bytes()).hexdigest() for p in paths}
    if before != after:
        raise ValueError("Observed contract or frozen result changed during comparison")
    result["input_sha256"] = before
    result["runner_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.open("x").write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").open("x").write(
        sha256(args.output.read_bytes()).hexdigest() + "\n"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "case_count",
                    "declared_input_rejected_cases",
                    "connected_declared_output_rejected_cases",
                    "current_output_rejected_cases",
                    "declared_contract_compatible",
                )
            }
        )
    )
    return int(args.require_compatible and not result["declared_contract_compatible"])


if __name__ == "__main__":
    raise SystemExit(main())
