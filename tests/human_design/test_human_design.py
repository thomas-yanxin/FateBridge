"""Independent astronomy, exact boundary arithmetic and graph counterexamples."""

import json
import math
import random
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro import runtime
from fatebridge.core.human_design import (
    bodygraph,
    chart_at,
    longitude_activation,
    planetary_positions,
)
from fatebridge.core.human_design_evidence import reference_table_audit
from fatebridge.core.human_design_mechanics import CENTER_GATES, CHANNELS, GATE_ORDER
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.services.human_design import calculate_human_design

ROOT = Path(__file__).resolve().parents[2]
INPUT = dict(
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="Asia/Shanghai",
)


def test_structure_is_complete_without_duplicate_gate_or_channel():
    assert sorted(GATE_ORDER) == list(range(1, 65))
    assert sorted(g for gates in CENTER_GATES.values() for g in gates) == list(
        range(1, 65)
    )
    assert len({frozenset((a, b)) for a, b, _ in CHANNELS}) == 36
    assert all(a != b for a, b, _ in CHANNELS)


@pytest.mark.parametrize(
    "degrees,gate,line",
    [
        (302, 41, 1),
        (358.25, 25, 1),
        (0, 25, 2),
        (3.875, 17, 1),
        (58.25, 8, 5),
        (223.25, 1, 1),
        (301.999, 60, 6),
    ],
)
def test_hand_checked_mandala_anchors(degrees, gate, line):
    actual = longitude_activation(degrees)
    assert (actual["gate"], actual["line"]) == (gate, line)


def test_every_gate_and_line_boundary_and_adjacent_float():
    # Gate and line widths (5.625 and .9375) are exactly binary representable.
    for i, gate in enumerate(GATE_ORDER):
        for line in range(6):
            lon = (302 + i * 5.625 + line * 0.9375) % 360
            exact = longitude_activation(lon)
            assert (
                exact["gate"],
                exact["line"],
                exact["color"],
                exact["tone"],
                exact["base"],
            ) == (gate, line + 1, 1, 1, 1)
            before = longitude_activation(math.nextafter(lon, -math.inf))
            after = longitude_activation(math.nextafter(lon, math.inf))
            assert (after["gate"], after["line"]) == (gate, line + 1)
            assert (before["gate"], before["line"]) != (gate, line + 1)


def test_subdivision_against_independent_rational_reference():
    # An arithmetic check, not an independent source for the mandala's gate order.
    randomizer = random.Random(86720)
    values = [randomizer.uniform(-1080, 1080) for _ in range(2000)]
    values += [(302 + i / 192) % 360 for i in range(69120)]
    for value in values:
        phase = ((Fraction(value) - 302) % 360) / Fraction(45, 8)
        expected = []
        for count in (64, 6, 6, 6, 5):
            # First phase already measured in gates; next phases are fractional.
            index = int(phase)
            expected.append(index)
            phase = (phase - index) * (6 if len(expected) < 4 else 5)
        actual = longitude_activation(value)
        assert [actual[k] for k in ("gate", "line", "color", "tone", "base")] == [
            GATE_ORDER[expected[0]],
            *(x + 1 for x in expected[1:]),
        ]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_longitudes_rejected(value):
    with pytest.raises(ValueError):
        longitude_activation(value)


@pytest.mark.parametrize(
    "gates,type_id,subtype,authority",
    [
        ([1], "reflector", None, "lunar_no_inner_authority"),
        ([5, 15], "generator", "pure_generator", "sacral"),
        ([5, 15, 1, 8], "generator", "manifesting_generator", "sacral"),
        # Sacral and throat disconnected from one another, but another motor has a throat path.
        ([5, 15, 21, 45], "generator", "manifesting_generator", "sacral"),
        ([21, 45], "manifestor", None, "ego_manifested"),
        ([25, 51], "projector", None, "ego_projected"),
        ([1, 8], "projector", None, "self_projected"),
        ([17, 62], "projector", None, "environment_no_inner_authority"),
        ([18, 58], "projector", None, "splenic"),
        ([5, 15, 19, 49], "generator", "pure_generator", "emotional"),
        ([12, 22], "manifestor", None, "emotional"),
        # Indirect motor-to-throat connectivity must count.
        ([25, 51, 1, 8], "manifestor", None, "ego_manifested"),
    ],
)
def test_type_authority_hierarchy_with_counterexamples(
    gates, type_id, subtype, authority
):
    graph = bodygraph(gates, [])
    assert (graph["type"], graph["subtype"], graph["authority"]) == (
        type_id,
        subtype,
        authority,
    )


def test_definition_uses_union_of_sides_not_separate_channel_counts():
    graph = bodygraph([5], [15])
    assert graph["type"] == "generator"
    assert graph["channels"][0]["mixed_only"] is True
    assert graph["gate_sources"] == {"5": ["personality"], "15": ["design"]}
    dormant = bodygraph([1], [])
    assert dormant["centers"]["g"]["status"] == "undefined"
    assert dormant["centers"]["head"]["status"] == "completely_open"
    assert dormant["definition"]["kind"] == "none"


def test_four_disconnected_components_and_single_gate_bridges():
    graph = bodygraph([64, 47, 16, 48, 25, 51, 19, 49], [])
    assert graph["definition"]["kind"] == "quadruple_split"
    for gate in graph["definition"]["single_gate_bridges"]:
        assert (
            len(
                bodygraph(graph["activated_gates"] + [gate], [])["definition"][
                    "components"
                ]
            )
            < 4
        )
    joined = bodygraph([64, 47, 16, 48, 25, 51, 19, 49, 1], [])
    assert 8 in joined["definition"]["single_gate_bridges"]


@pytest.mark.parametrize("month,day", [(1, 1), (3, 20), (6, 21), (9, 22), (12, 31)])
def test_design_epoch_solar_arc_across_seasons_and_wrap(month, day):
    birth = datetime(2000, month, day, 12, tzinfo=timezone.utc)
    chart = chart_at(birth)
    solar = {
        side: next(a["longitude"] for a in values if a["body"] == "Sun")
        for side, values in chart["activations"].items()
    }
    assert (solar["personality"] - solar["design"]) % 360 == pytest.approx(88, abs=1e-7)
    assert chart["design_solver"]["bracket_width_seconds"] <= 0.001
    assert abs(chart["design_solver"]["days_before_birth"] - 88) > 0.05
    for side in chart["activations"].values():
        assert len(side) == 13
        by_body = {a["body"]: a for a in side}
        assert (
            by_body["Earth"]["longitude"] - by_body["Sun"]["longitude"]
        ) % 360 == pytest.approx(180)
        assert (
            by_body["SouthNode"]["longitude"] - by_body["NorthNode"]["longitude"]
        ) % 360 == pytest.approx(180)


def test_independent_jpl_positions_not_engine_generated_expected_values():
    data = json.loads((ROOT / "tests/fixtures/western-horizons.json").read_text())
    by_epoch = {}
    for reference in data["references"]:
        for row in reference["rows"]:
            # Horizons pre-1962 labels are UT1, matching our historical input
            # assumption; 1969 is actual UTC and uses the IERS drift table.
            moment = row["utc"]
            if moment not in by_epoch:
                by_epoch[moment] = planetary_positions(datetime.fromisoformat(moment))[
                    "positions"
                ]
            actual = by_epoch[moment][reference["body"]]["longitude"]
            error = (
                abs((actual - row["apparent_ecliptic_longitude"] + 180) % 360 - 180)
                * 3600
            )
            assert error <= data["tolerance_arcseconds"], (
                moment,
                reference["body"],
                error,
            )


def test_independent_jpl_checks_design_solar_arc():
    data = json.loads((ROOT / "tests/fixtures/human-design-horizons.json").read_text())
    rows = {row["utc"]: row["sun_longitude"] for row in data["rows"]}
    assert len(rows) == 8 and len(data["pairs"]) == 4
    for pair in data["pairs"]:
        arc = (rows[pair["birth_utc"]] - rows[pair["design_candidate_utc"]]) % 360
        assert abs(arc - 88) * 3600 <= data["tolerance_arcseconds"]


def test_official_example_bodygraph_from_independently_transcribed_activations():
    data = json.loads(
        (ROOT / "tests/fixtures/human-design-official-example.json").read_text()
    )
    graph = bodygraph(
        (a["gate"] for a in data["activations"]["personality"].values()),
        (a["gate"] for a in data["activations"]["design"].values()),
    )
    expected = data["structure"]
    assert graph["type"] == expected["type"]
    assert graph["authority"] == expected["authority"]
    assert graph["definition"]["components"] == expected["definition_components"]
    assert sorted(sorted(c["gates"]) for c in graph["channels"]) == expected["channels"]


def test_official_example_26_gate_lines_at_declared_nominal_birth_clock():
    data = json.loads(
        (ROOT / "tests/fixtures/human-design-official-example.json").read_text()
    )
    # Birth clock is a declared assumption, not authenticated by the source figure.
    chart = chart_at(datetime.fromisoformat(data["nominal_birth_utc"]), "true")
    assert chart["profile"] == data["structure"]["profile"]
    for side, items in chart["activations"].items():
        actual = {a["body"]: {k: a[k] for k in ("gate", "line")} for a in items}
        assert actual == data["activations"][side]
    alternative = chart_at(datetime.fromisoformat(data["nominal_birth_utc"]), "mean")
    changed = [
        (side, a["body"])
        for side, items in alternative["activations"].items()
        for a in items
        if a["line"] != data["activations"][side][a["body"]]["line"]
    ]
    assert set(changed) == {
        (side, body)
        for side in ("personality", "design")
        for body in ("NorthNode", "SouthNode")
    }


def test_primary_source_numeric_tables_preserve_unresolved_discrepancy():
    report = reference_table_audit()
    assert report["gate_ranges_matched"] == report["gate_ranges_checked"] == 64
    assert report["centers_matched"] == 64
    assert report["channel_pairs_matched"] == 36
    assert report["channel_pair_sets_equal"]
    # These are acceptance failures in the source report, not passed assertions.
    # Freeze the observed mismatch; do not rewrite the source to make it agree.
    assert report["line_ranges_matched"] == 382
    assert report["line_ranges_checked"] == 384
    assert {(d["gate"], d["line"]) for d in report["discrepancies"]} == {
        (29, 1),
        (29, 2),
    }
    assert report["status"] == "unresolved_source_discrepancies"
    assert report["full_text_acceptance_passed"] is False


def test_29_1_2_choice_is_explicit_uniform_rule_not_hidden_source_rewrite():
    # Printed 25d16m15s Leo conflicts with the uniform 56m15s line width.
    assert longitude_activation(145.3)["line"] == 1
    report = reference_table_audit()
    assert report["discrepancies"][0]["printed_range"][
        "end_longitude"
    ] == pytest.approx(145 + 16 / 60 + 15 / 3600)
    assert (
        report["discrepancies"][0]["implemented_uniform_range"]["end_longitude"]
        == 145.4375
    )


def test_source_audit_cannot_pass_after_reference_cases_are_deleted(monkeypatch):
    from fatebridge.core import human_design_evidence as module

    truncated = deepcopy(module.source_reference())
    truncated["gates"] = truncated["gates"][:1]
    monkeypatch.setattr(module, "source_reference", lambda: truncated)
    report = module.reference_table_audit()
    assert report["status"] == "numeric_table_mismatch"
    assert report["numeric_table_acceptance_passed"] is False
    assert report["full_text_acceptance_passed"] is False


@pytest.mark.parametrize("removed", ["birth_hour", "birth_minute", "birth_timezone"])
def test_no_default_for_unknown_time_or_timezone(removed):
    with pytest.raises(ValidationError):
        HumanDesignRequest(**{k: v for k, v in INPUT.items() if k != removed})


@pytest.mark.parametrize(
    "changes",
    [
        {"birth_day": 31},
        {"birth_year": 2023, "birth_month": 2, "birth_day": 29},
        {"birth_timezone": "Unknown/Nowhere"},
        {"node_mode": "whichever_fits"},
        {"birth_hour": None},
        {"use_true_solar_time": True},
        {
            "birth_year": 2024,
            "birth_month": 3,
            "birth_day": 10,
            "birth_hour": 2,
            "birth_timezone": "America/New_York",
        },
        {
            "birth_year": 2024,
            "birth_month": 11,
            "birth_day": 3,
            "birth_hour": 1,
            "birth_timezone": "America/New_York",
        },
    ],
)
def test_bad_calendar_dst_and_unrelated_solar_rebasing_rejected(changes):
    with pytest.raises((ValueError, ValidationError)):
        HumanDesignRequest(**{**INPUT, **changes})


def test_civil_timezone_equivalence_and_sensitivity_scope():
    local = calculate_human_design(**INPUT, birth_time_uncertainty_minutes=10)
    utc = calculate_human_design(**{**INPUT, "birth_hour": 1, "birth_timezone": "UTC"})
    assert local["activations"] == utc["activations"]
    assert local["time_sensitivity"]["status"] == "grid_and_station_candidates_compared"
    assert local["time_sensitivity"]["sampling"]["grid_sample_count"] == 121
    assert (
        local["time_sensitivity"]["sampling"]["continuous_interval_certified"] is False
    )
    assert len(local["time_sensitivity"]["comparisons"]) == 2
    assert utc["time_sensitivity"]["status"] == "not_assessed"
    assert local["validation"]["prediction"] == "not_validated"
    assert local["validation"]["all_four_axes_full_marks"] is False


@pytest.mark.native_engine_fault
def test_missing_ephemeris_fails_without_low_precision_fallback(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    result = calculate_human_design(**INPUT)
    assert "error" in result
    assert "bodygraph" not in result


def test_returned_source_evidence_cannot_mutate_later_runs():
    first = calculate_human_design(**INPUT)
    original = deepcopy(first["gate_evidence"])
    first["gate_evidence"][0]["source_channel_pairs"][0][0] = -1
    first["gate_evidence"][0]["source_pdf_pages_one_based"].clear()
    first["rulesets"][0]["sources"]["rave_2001"] = "changed"
    second = calculate_human_design(**INPUT)
    assert second["gate_evidence"] == original
    assert second["rulesets"][0]["sources"]["rave_2001"].startswith("https://")


def test_moshier_is_explicit_and_can_be_refused(monkeypatch, tmp_path):
    from fatebridge.application.execution import execute_tool
    from fatebridge.services.tool_catalog import CATALOG
    from tests.support.ephemeris_context import moshier_ephemeris

    spec = next(s for s in CATALOG if s.key == "human_design")
    with moshier_ephemeris():
        result = execute_tool(spec, HumanDesignRequest(**INPUT))
        assert result["calculation_policy"]["ephemeris_model"] == "moshier"
        assert result["run_metadata"]["engine_is_approximate"] is True
        failure = calculate_human_design(**INPUT, require_swiss_files=True)
        assert "error" in failure
        assert "bodygraph" not in failure


@pytest.mark.parametrize("flag,longitude", [(-1, float("nan")), (0, 100.0)])
@pytest.mark.native_engine_fault
def test_native_invalid_retflag_and_nonfinite_position_not_accepted(
    monkeypatch, flag, longitude
):
    def invalid(operation, *args):
        if operation == "calc":
            return (longitude, 0, 0, 0, 0, 0), flag
        return original(operation, *args)

    original = runtime.ephemeris_call
    monkeypatch.setattr(runtime, "ephemeris_call", invalid)
    assert "error" in calculate_human_design(**INPUT)
    with pytest.raises(RuntimeError):
        planetary_positions(datetime(2000, 1, 1, tzinfo=timezone.utc))
