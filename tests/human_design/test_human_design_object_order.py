"""Object key permutations preserve receipts; arrays and values remain strict."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design import longitude_activation
from fatebridge.core.human_design_depth import line_fixings
from fatebridge.core.human_design_source_variants import line_variant_impact
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from tests.human_design.test_human_design_publisher import current as current

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "tests/fixtures/human-design-object-order-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def forbidden(*args, **kwargs):
    raise AssertionError("Object-order replay called a native producer")


def permute(value, order):
    if isinstance(value, dict):
        keys = sorted(value) if order == "sorted" else list(reversed(value))
        return {k: permute(value[k], order) for k in keys}
    if isinstance(value, list):
        return [permute(v, order) for v in value]
    return value


def test_both_recipient_and_donor_sides_have_explicit_order_with_array_indices():
    sides = {
        "personality": [
            {"body": "Sun", "gate": 55, "line": 2},
            {"body": "Venus", "gate": 39, "line": 1},
        ],
        "design": [
            {"body": "Moon", "gate": 55, "line": 2},
            {"body": "Venus", "gate": 39, "line": 4},
        ],
    }
    before = line_fixings(sides)
    reordered = line_fixings(
        {"design": sides["design"], "personality": sides["personality"]}
    )
    assert before == reordered
    assert [(r["side"], r["body"]) for r in reordered] == [
        ("personality", "Sun"),
        ("personality", "Venus"),
        ("design", "Moon"),
        ("design", "Venus"),
    ]
    recipient = next(
        r for r in reordered if r["side"] == "personality" and r["body"] == "Sun"
    )
    donors = recipient["fixing_planets"]["exaltation"]
    assert [
        (d["side"], d["gate"], d["line"], d["calculation_path"]) for d in donors
    ] == [
        ("personality", 39, 1, "activations.personality.1"),
        ("design", 39, 4, "activations.design.1"),
    ]


def test_source_29_disagreement_lists_are_independent_of_side_object_order():
    a = {"body": "Moon", **longitude_activation(145.3)}
    p = {"activations": {"personality": [a], "design": [deepcopy(a)]}}
    d = {"activations": {"design": [deepcopy(a)], "personality": [a]}}
    first = line_variant_impact(p)
    assert first == line_variant_impact(d)
    assert [r["calculation_path"] for r in first["differences"]] == [
        "activations.personality.0",
        "activations.design.0",
    ]
    assert (
        first["conditional_printed_line_effects"]["full_alternative_chart_computed"]
        is False
    )


@pytest.mark.parametrize("order", ["sorted", "reversed"])
@pytest.mark.parametrize("index", range(16))
def test_all_frozen_publisher_runs_keep_facts_and_full_reading_when_maps_reorder(
    index, order, current  # noqa: F811 - pytest fixture dependency
):
    RUNS, _ = current
    original = RUNS[index]["run"]
    reordered = permute(original, order)
    # Object-key order does not change facts; array order remains significant.
    assert reordered == original
    assert (
        reordered["activations"]["personality"]
        == original["activations"]["personality"]
    )
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert (
            verify_human_design_reading(reordered)["status"]
            == "verified_fixed_template_reading"
        )


@pytest.mark.parametrize("kind", PLAN["negative_cases"])
def test_rehashed_array_or_value_changes_still_reject_after_map_sorting(
    kind, current
):  # noqa: F811 - pytest fixture dependency
    RUNS, _ = current
    # Select an actual frozen chart with multiple donors, so the donor-order
    # mutation is real rather than reversing an empty or one-item array.
    source = next(
        r["run"]
        for r in RUNS
        if any(
            len(v) > 1
            for row in r["run"]["depth_evidence"]["line_fixings"]
            for v in row["fixing_planets"].values()
        )
    )
    run = deepcopy(source)
    records = run["depth_evidence"]["line_fixings"]
    if kind == "activation_array_order":
        run["activations"]["personality"][0:2] = reversed(
            run["activations"]["personality"][0:2]
        )
    elif kind == "fixing_array_order":
        records.reverse()
    elif kind == "donor_array_order":
        donors = next(
            v for r in records for v in r["fixing_planets"].values() if len(v) > 1
        )
        donors.reverse()
    elif kind == "wrong_type":
        run["activations"]["personality"][0]["gate"] = True
    elif kind == "wrong_path":
        records[0]["calculation_path"] = "activations.design.0"
    elif kind == "wrong_source":
        records[0]["source_pdf_page_one_based"] += 1
    else:
        records[0]["reading"] = "Complete original line meaning accepted"
    run = permute(run, "sorted")
    assert run != source
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert verify_human_design_reading(run)["status"] == "rejected"


def test_current_complete_cycle_context_replays_with_reordered_objects(monkeypatch):
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    run = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=1980,
            birth_month=1,
            birth_day=1,
            birth_hour=0,
            birth_minute=0,
            birth_timezone="UTC",
            cycle_reference_datetime="2030-01-01T00:00:00Z",
        ),
    )
    assert run["cycle_context"]["status"] in ("computed_finite_search", "partial")
    assert run["cycle_context"]["source_evidence"]
    for order in ("sorted", "reversed"):
        transformed = permute(run, order)
        with (
            patch.object(runtime, "ephemeris_call", forbidden),
            patch.object(native_execution, "calculate", forbidden),
        ):
            result = verify_human_design_reading(transformed)
        assert result["checked_cycle_evaluation_count"] > 0
        assert result["status"] == "verified_fixed_template_reading", result
