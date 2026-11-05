"""Audit complete-result attribution, retaining all frozen rows and controls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_request_binding_v3"
PIN = "c3f0fa35bb0eaa078fa3350435559484f08bb8cbec47a4754da6f24266178184"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    def checked(folder: Path, pin: str) -> dict[str, Any]:
        if sha(folder / "freeze.json") != pin:
            raise ValueError("Frozen request-binding reference changed")
        frozen = json.loads((folder / "freeze.json").read_text())
        if {p.name for p in folder.iterdir()} != set(frozen["files"]) | {"freeze.json"}:
            raise ValueError("Frozen request-binding inventory changed")
        if any(sha(folder / n) != digest for n, digest in frozen["files"].items()):
            raise ValueError("Frozen request-binding source bytes changed")
        result: dict[str, Any] = json.loads((folder / "reference.json").read_text())
        return result

    ref = checked(corpus, PIN)
    prior = checked(
        ROOT / "tests/fixtures/ren_request_binding_v2", ref["previous_reference_pin"]
    )
    checked(
        ROOT / "tests/fixtures/ren_request_binding_v1", prior["original_reference_pin"]
    )
    if len(ref["probes"]) != 70 or ref["expected_fault_probe_count"] != 68:
        raise ValueError("Frozen request-binding denominators changed")
    return ref


def audit(capture_dir: Path) -> dict[str, Any]:
    from fatebridge.application.execution import (
        OutputContractError,
        execute_spec,
        validate_output,
    )
    from fatebridge.core.execution_context import call_clock
    from fatebridge.services.tool_catalog import CATALOG

    ref = reference()
    capture_dir.mkdir()
    specs = {spec.key: spec for spec in CATALOG}
    cached: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    def produced(
        key: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        identity = key + json.dumps(payload, sort_keys=True)
        if identity not in cached:
            spec = specs[key]
            request = spec.request_model.model_validate(payload)
            fn, args, kwargs = spec.bind(request)
            with call_clock("2026-10-12T02:00:00Z"):
                value = fn(*args, **kwargs)
            if "error" in value:
                raise ValueError(
                    "A declared coherent request returned an error: " + identity
                )
            validate_output(spec, value)
            file = capture_dir / ("value-" + str(len(cached)).zfill(3) + ".json")
            file.write_text(
                json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            )
            cached[identity] = (value, dict(file=file.name, sha256=sha(file)))
        return cached[identity]

    rows = []
    for row in ref["probes"]:
        spec = specs[row["key"]]
        target = row["returned_request"]
        outcome = row["expected"]
        if outcome == "request_schema_rejects_unsupported_field_before_service":
            try:
                spec.request_model.model_validate(target)
            except ValidationError:
                passed = True
            else:
                passed = False
            rows.append(
                dict(id=row["id"], kind="unsupported_field_control", passed=passed)
            )
            continue
        if outcome == "service_rejects_offset_inconsistent_with_historical_zone":
            req = spec.request_model.model_validate(target)
            fn, args, kwargs = spec.bind(req)
            value = fn(*args, **kwargs)
            passed = (
                value.get("error_code") == "validation_error"
                and value.get("status_code") == 400
            )
            rows.append(
                dict(
                    id=row["id"],
                    kind="invalid_offset_control",
                    passed=passed,
                    result=value,
                )
            )
            continue
        request = spec.request_model.model_validate(row["request"])
        original, original_capture = produced(spec.key, row["request"])
        foreign, foreign_capture = produced(spec.key, target)
        if original == foreign:
            raise ValueError("Counterfactual must have a distinct complete result")

        def foreign_bind(
            _request: BaseModel,
        ) -> tuple[Callable[..., dict[str, Any]], tuple, dict[str, Any]]:
            def foreign_service() -> dict[str, Any]:
                return copy.deepcopy(foreign)

            return foreign_service, (), {}

        broken = replace(spec, bind=foreign_bind)
        detail: str | None
        try:
            execute_spec(broken, request)
        except OutputContractError as error:
            verdict = "rejected"
            detail = str(error)
        except Exception as error:
            verdict = "wrong_error_type"
            detail = type(error).__name__ + ": " + str(error)
        else:
            verdict = "accepted"
            detail = None
        rows.append(
            dict(
                id=row["id"],
                kind="coherent_result_swap",
                verdict=verdict,
                own_result_valid=True,
                original=original_capture,
                foreign=foreign_capture,
                error=detail,
            )
        )
        (capture_dir / "partial-ledger.json").write_text(
            json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )

    positives = []
    for identity, (value, capture) in cached.items():
        # The identity is a key followed by canonical JSON, never an eval expression.
        key, encoded = identity.split("{", 1)
        spec = specs[key]
        request = spec.request_model.model_validate(json.loads("{" + encoded))
        with call_clock("2026-10-12T02:00:00Z"):
            actual = execute_spec(spec, request)
        positives.append(dict(result=capture, unchanged=actual == value))
    faults = [r for r in rows if r["kind"] == "coherent_result_swap"]
    controls = [r for r in rows if r["kind"] != "coherent_result_swap"]
    return dict(
        reference_pin=PIN,
        reference_is_blind=False,
        reference_timing=(
            "v1 predates all probes. v2 fixed an unsupported field before swap execution. "
            "v3 retained the invalid historical-offset control and added a valid one after "
            "a partial old-code run, before production edits. Its inherited "
            "before_fault_probe_execution flag is too broad; it is not a blind reference."
        ),
        total_frozen_rows=len(rows),
        coherent_fault_probes=len(faults),
        rejected=sum(r["verdict"] == "rejected" for r in faults),
        accepted=sum(r["verdict"] == "accepted" for r in faults),
        wrong_error_types=sum(r["verdict"] == "wrong_error_type" for r in faults),
        invalid_input_controls=controls,
        normal_complete_results=positives,
        all_positive_business_bytes_preserved=all(p["unchanged"] for p in positives),
        rows=rows,
        new_classical_cases=0,
        new_empirical_outcomes=0,
        automatic_language_semantic_acceptance=False,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(
            "Use an unused output path; existing evidence must not be overwritten"
        )
    report = audit(args.output.with_name(args.output.stem + "-results"))
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "total_frozen_rows",
                    "coherent_fault_probes",
                    "rejected",
                    "accepted",
                    "wrong_error_types",
                    "all_positive_business_bytes_preserved",
                ]
            }
        )
    )
    return int(
        not (
            report["rejected"] == 68
            and report["coherent_fault_probes"] == 68
            and len(report["normal_complete_results"]) == 72
            and report["all_positive_business_bytes_preserved"]
            and all(r["passed"] for r in report["invalid_input_controls"])
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
