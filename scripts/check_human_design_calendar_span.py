"""Compare every new seasonal stratum without replacing the original cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from fatebridge.core.human_design import longitude_activation, positions_at_tt
from fatebridge.core.human_design_natal_sources import guard_natal_sources
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.human_design_time import solve_design_epoch_tt

ROOT = Path(__file__).resolve().parents[1]
BINDINGS = {
    "tests/fixtures/human-design-calendar-span-plan.json": "8dd18b55006024128f42efe5ab8671db4a4fd4ac76fbb23a593146289d957f86",
    "tests/fixtures/human-design-calendar-span-de440.json": "06ef8f4e29842187f7916734006d7c56467ead52a7f23797865912a5a5b14411",
    "scripts/gen_human_design_calendar_span_reference.py": "428b7ae1c5a067662fbefea56b3ef8a08f303a6a2eebf5211bfda40a9983d09d",
    "tests/fixtures/human-design-astronomy-plan.json": "14475d33b6b664b8d1a7b9aaa746352ca5aaced242735f5e39c6e75dac129f50",
    "tests/fixtures/human-design-astronomy-de440.json": "949d4187a8bc6c4bacd8492a374c523d788cc72e73842c8e231850ff786733ca",
    "scripts/gen_human_design_astronomy_reference.py": "c37337a83dd976b601d431fb40ca1ffe2e95cdf88980f42ba65090588740c1c1",
}


def reference(root: Path) -> tuple[dict, dict]:
    for path, sha in BINDINGS.items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != sha:
            raise ValueError("Frozen calendar reference changed: " + path)
    plan = json.loads((root / next(iter(BINDINGS))).read_text())
    data = json.loads(
        (root / "tests/fixtures/human-design-calendar-span-de440.json").read_text()
    )
    if (
        len(data["pairs"]) != 1200
        or len(plan["birth_epochs"]) != 1200
        or plan["comparison_tolerance_arcseconds"] != 2.0
        or plan["design_root_time_tolerance_seconds"] != 5.0
    ):
        raise ValueError("All frozen strata and original tolerances are required")
    for fixed, pair in zip(plan["birth_epochs"], data["pairs"]):
        if fixed != {"label": pair["label"], "jd_tt": pair["personality"]["jd_tt"]}:
            raise ValueError("Calendar stratum detached from independent reference")
        for side in ("personality", "design"):
            if set(pair[side]["positions"]) != set(plan["bodies"]) or any(
                fact["target_id"] != plan["bodies"][body]
                for body, fact in pair[side]["positions"].items()
            ):
                raise ValueError("Independent physical targets changed")
    return plan, data


def _error(exc: Exception) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _finite(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _position_row(
    pair: dict,
    side: str,
    body: str,
    fact: dict,
    backend: str,
    actual: dict | None,
    calculation_error: Exception | None,
) -> dict:
    epoch, expected = pair[side]["jd_tt"], fact["longitude"]
    row: dict[str, Any] = {
        "label": pair["label"],
        "side": side,
        "body": body,
        "jd_tt": epoch,
        "native_model": None,
        "return_flags": None,
        "computed_longitude": None,
        "reference_longitude": expected,
        "error_arcseconds": None,
        "within_tolerance": False,
        "different_levels_using_current_mapping": None,
        "evaluation_status": "not_assessed_calculation_error",
        "backend_status": "not_assessed",
        "backend_accepted": False,
    }
    try:
        if calculation_error is not None:
            raise calculation_error
        assert actual is not None
        value = actual[body]
        computed = value["longitude"]
        if not _finite(computed) or not 0 <= computed < 360:
            raise ValueError("Nonfinite or out-of-range native longitude")
        row["computed_longitude"] = computed
        error = abs((computed - expected + 180) % 360 - 180) * 3600
        classifications = [longitude_activation(x) for x in (computed, expected)]
        row.update(
            {
                "error_arcseconds": error,
                "within_tolerance": error <= 2.0,
                "different_levels_using_current_mapping": [
                    key
                    for key in ("gate", "line", "color", "tone", "base")
                    if classifications[0][key] != classifications[1][key]
                ],
                "evaluation_status": "observed",
            }
        )
        model, flags = value.get("ephemeris_model"), value.get("return_flags")
        if type(model) is str:
            row["native_model"] = model
        if type(flags) is int:
            row["return_flags"] = flags
        if position_flag_model(flags) != model:
            raise ValueError("Native model and actual returned flags disagree")
        row["backend_accepted"] = model == backend
        row["backend_status"] = (
            "matches_requested" if model == backend else "different_actual_backend"
        )
    except Exception as exc:
        row["error"] = _error(exc)
        if row["evaluation_status"] == "observed":
            row["backend_status"] = "invalid_or_missing_backend_observation"
    row["accepted"] = row["within_tolerance"] and row["backend_accepted"]
    return row


@guard_natal_sources
def _root_result(epoch: float, backend: str) -> dict:
    # The existing observer records the calls already made by the original
    # solver; it neither requests new coordinates nor changes the solver.
    return solve_design_epoch_tt(epoch, backend=backend)


def _root_row(pair: dict, backend: str) -> dict:
    row: dict[str, Any] = {
        "label": pair["label"],
        "computed_jd_tt": None,
        "reference_jd_tt": pair["design"]["jd_tt"],
        "error_seconds": None,
        "within_tolerance": False,
        "evaluation_status": "not_assessed_calculation_error",
        "backend_status": "not_assessed",
        "backend_accepted": False,
    }
    try:
        result = _root_result(pair["personality"]["jd_tt"], backend)
        computed = result["solver"]["design_jd_tt"]
        if not _finite(computed):
            raise ValueError("Nonfinite design root TT")
        row["computed_jd_tt"] = computed
        error = abs(computed - row["reference_jd_tt"]) * 86400
        if not math.isfinite(error):
            raise ValueError("Nonfinite design root comparison error")
        row.update(
            {
                "computed_jd_tt": computed,
                "error_seconds": error,
                "within_tolerance": error <= 5.0,
                "evaluation_status": "observed",
            }
        )
        source = result["ephemeris_source_evidence"]
        row["source_evidence"] = source
        contexts = source["contexts"]
        valid = bool(contexts) and all(
            c["body"] == "Sun"
            and c["role"] == "solar_root"
            and type(c["observed_evaluation_count"]) is int
            and c["observed_evaluation_count"] > 0
            for c in contexts
        )
        if not valid:
            row["backend_status"] = "not_assessed_missing_solar_observations"
        else:
            row["backend_accepted"] = all(
                c["native_return_flag_model"] == backend for c in contexts
            )
            row["backend_status"] = (
                "matches_requested"
                if row["backend_accepted"]
                else "different_actual_backend"
            )
    except Exception as exc:
        row["error"] = _error(exc)
    row["accepted"] = row["within_tolerance"] and row["backend_accepted"]
    return row


def checks(root: Path = ROOT) -> dict:
    plan, data = reference(root)
    backends = {}
    for label, backend in (("selected", "swieph"), ("moshier_diagnostic", "moshier")):
        rows, roots = [], []
        for pair in data["pairs"]:
            for side in ("personality", "design"):
                epoch = pair[side]["jd_tt"]
                actual = None
                calculation_error = None
                try:
                    actual = positions_at_tt(epoch, "true", backend=backend)
                except Exception as exc:
                    calculation_error = exc
                for body, fact in pair[side]["positions"].items():
                    rows.append(
                        _position_row(
                            pair, side, body, fact, backend, actual, calculation_error
                        )
                    )
            roots.append(_root_row(pair, backend))
        failures = [r for r in rows if not r["within_tolerance"]]
        root_failures = [r for r in roots if not r["within_tolerance"]]
        observed = [r for r in rows if r["evaluation_status"] == "observed"]
        observed_roots = [r for r in roots if r["evaluation_status"] == "observed"]
        maximum = max(observed, key=lambda r: r["error_arcseconds"], default=None)
        backends[label] = {
            "status": (
                "bounded_match"
                if all(r["accepted"] for r in [*rows, *roots])
                else "failed"
            ),
            "position_count": len(rows),
            "positions_matched": len(rows) - len(failures),
            "position_failure_count": len(failures),
            "position_failures_by_body": dict(
                sorted(Counter(r["body"] for r in failures).items())
            ),
            "maximum_position_error_arcseconds": (
                maximum["error_arcseconds"] if maximum is not None else None
            ),
            "maximum_position_error_row": maximum,
            "root_count": len(roots),
            "roots_matched": len(roots) - len(root_failures),
            "maximum_root_error_seconds": max(
                (r["error_seconds"] for r in observed_roots), default=None
            ),
            "position_not_assessed_count": len(rows) - len(observed),
            "root_not_assessed_count": len(roots) - len(observed_roots),
            "position_backend_unaccepted_count": sum(
                not r["backend_accepted"] for r in rows
            ),
            "root_backend_unaccepted_count": sum(
                not r["backend_accepted"] for r in roots
            ),
            "position_accepted_count": sum(r["accepted"] for r in rows),
            "root_accepted_count": sum(r["accepted"] for r in roots),
            "position_backend_failures": [r for r in rows if not r["backend_accepted"]],
            "root_backend_failures": [r for r in roots if not r["backend_accepted"]],
            "position_rows": rows,
            "root_rows": roots,
            "position_failures": failures,
            "root_failures": root_failures,
        }
    return {
        "method_id": "human_design_additional_seasonal_de440_checks_v2",
        "reference_bindings": BINDINGS,
        "birth_epochs": 1200,
        "supported_years_sampled": list(range(1800, 2400)),
        "position_tolerance_arcseconds": 2.0,
        "root_tolerance_seconds": 5.0,
        "status": (
            "failed"
            if any(v["status"] == "failed" for v in backends.values())
            else "additional_bounded_match"
        ),
        "backends": backends,
        "complete_calendar_acceptance": False,
        "subdivision_critical_accuracy_certified": False,
        "scope": plan["scope"],
        "authority_certified": False,
        "backend_acceptance_scope": "Original numerical comparisons retained separately. Bounded acceptance also requires actual position flags and all observed Sun-root backend contexts to match the requested backend; missing observations are unknown, never inferred from the request. Source observations do not authenticate native execution or celestial accuracy.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-acceptance", action="store_true")
    args = parser.parse_args()
    result = checks()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return int(
        result["status"] == "failed"
        or args.require_full_acceptance
        and not result["complete_calendar_acceptance"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
