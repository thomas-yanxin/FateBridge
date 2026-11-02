"""Run the frozen and preregistered actual-service clock acceptance probes."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path


def regression_checks() -> dict:
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.human_design_sample_witness import unpack_sample_witnesses
    from fatebridge.core.human_design_sensitivity import assess_birth_interval
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.human_design import verify_human_design_reading

    # The test harness holds the preregistered mutations; it does not provide
    # expected clock values or replace the production replay implementation.
    from tests.test_human_design_clock_replay import (
        BEFORE,
        MUTATIONS,
        mutate,
        rehash,
        set_path,
    )

    root = Path(__file__).resolve().parents[1]
    plan = root / "tests/fixtures/human-design-clock-replay-plan.json"
    if (
        hashlib.sha256(plan.read_bytes()).hexdigest()
        != "0e37c8c1e0f02cb82b58ca9db3984bc0d677b595620a34cf7d970cb925e921ea"
    ):
        raise ValueError("Preregistered clock replay criteria changed")
    spec = next(s for s in CATALOG if s.key == "human_design")
    original = execute_tool(
        spec, spec.request_model(**BEFORE["input"], birth_time_uncertainty_minutes=1)
    )
    controls = [verify_human_design_reading(original)]
    rows = []

    def check(case: str, value: dict) -> None:
        result = verify_human_design_reading(rehash(value))
        rows.append(
            {"id": case, "status": result["status"], "errors": result["errors"]}
        )

    for case in BEFORE["mutations"]:
        value = deepcopy(original)
        set_path(value, case["path"], case["replacement"])
        check(case["id"], value)
    before = json.loads(
        (root / "docs/validation/human-design-interval-clock-before.json").read_text()
    )
    value = deepcopy(original)
    set_path(value, before["mutation"]["path"], before["mutation"]["replacement"])
    raw = unpack_sample_witnesses(
        value["time_sensitivity"]["evaluation_witnesses"],
        value["calculation_policy"]["node_mode"],
        require_swiss_files=False,
        physical_backend_policy=value["calculation_policy"]["physical_backend_policy"],
    )
    value["time_sensitivity"] = assess_birth_interval(
        value,
        1,
        value["calculation_policy"]["node_mode"],
        _chart_reader=raw.__getitem__,
    )
    check("nonnominal_sample_UT1_entire_interval_rebuilt", value)
    for case in MUTATIONS:
        value = deepcopy(original)
        mutate(value, case)
        check(case, value)
    cycle = execute_tool(
        spec,
        spec.request_model(
            **BEFORE["input"], cycle_reference_datetime="2030-01-01T00:00:00Z"
        ),
    )
    controls.append(verify_human_design_reading(cycle))
    for case in (
        "cycle_reference_UTC",
        "cycle_contact_UTC",
        "cycle_contact_future_assumption",
    ):
        value = deepcopy(cycle)
        if case == "cycle_reference_UTC":
            value["cycle_context"]["reference_utc"] = "2031-01-01T00:00:00+00:00"
        else:
            event = next(
                r["contacts"][0]
                for r in value["cycle_context"]["bodies"]
                if r["contacts"]
            )
            if case == "cycle_contact_UTC":
                event["utc_label"] = "2031-01-01T00:00:00+00:00"
            else:
                event["future_leap_seconds_assumed_unchanged"] = not event[
                    "future_leap_seconds_assumed_unchanged"
                ]
        check(case, value)
    unresolved = [r["id"] for r in rows if r["status"] != "rejected"]
    return {
        "method_id": "human_design_clock_conversion_replay_regression_v1",
        "status": (
            "passed"
            if not unresolved
            and all(c["status"] == "verified_fixed_template_reading" for c in controls)
            else "failed"
        ),
        "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "cases": rows,
        "controls": controls,
        "unresolved": unresolved,
        "scope": "All9 original ordinary probes and the original nonnominalUT1 probe with the entire interval rebuilt, plus15 preregistered design/reference/cycle/observation contradictions. Fresh hashes throughout. Bounded internal conversion consistency only; not a native signature, measuredUT1, full supported-range external acceptance, original-source acceptance or prediction certificate.",
    }


if __name__ == "__main__":
    print(json.dumps(regression_checks(), ensure_ascii=False, indent=2))
