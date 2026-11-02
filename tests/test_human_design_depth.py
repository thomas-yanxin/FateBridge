"""Primary-source depth, physical-time edge cases and hostile reading changes."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.time_scales import datetime_from_tt, leap_table
from fatebridge.core.human_design import chart_at
from fatebridge.core.human_design_depth import (
    cross_identifier,
    depth_reference,
    line_fixings,
)
from fatebridge.core.human_design_evidence import source_activation_impacts
from fatebridge.core.human_design_time import sun_at_tt, utc_from_tt
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(spec for spec in CATALOG if spec.key == "human_design")


def test_source_depth_catalogue_is_complete_without_invented_dualities():
    data = depth_reference()
    numeric = json.loads(
        (ROOT / "src/fatebridge/data/human_design/rave-2001-reference.json").read_text()
    )
    assert data["source"]["pdf_sha256"] == numeric["source"]["pdf_sha256"]
    assert [row["gate"] for row in data["gates"]] == list(range(1, 65))
    assert sum(len(row["cross_identifiers"]) for row in data["gates"]) == 192
    assert (
        len(
            {
                tuple(c["gates"])
                for row in data["gates"]
                for c in row["channel_identifiers"]
            }
        )
        == 36
    )
    lines = [
        (row["gate"], line) for row in data["gates"] for line in row["line_polarities"]
    ]
    assert len(lines) == 384
    assert sum(line["polarity_kind"] == "dual" for _, line in lines) == 375
    assert {
        (gate, line["line"]) for gate, line in lines if line["polarity_kind"] != "dual"
    } == {
        (5, 6),
        (25, 4),
        (37, 1),
        (47, 5),
        (47, 6),
        (54, 4),
        (54, 5),
        (57, 3),
        (58, 2),
    }


@pytest.mark.parametrize(
    "gate,angle,name",
    [
        (1, "right", "THE SPHINX (4)"),
        (1, "juxtaposition", "SELF-EXPRESSION"),
        (1, "left", "DEFIANCE (2)"),
        (55, "left", "SPIRIT"),
        (29, "right", "CONTAGEN (3)"),
    ],
)
def test_cross_identifiers_match_primary_printed_names_including_original_spelling(
    gate, angle, name
):
    assert cross_identifier(gate, angle)["name"] == name


def activation(body, gate, line):
    return {"body": body, "gate": gate, "line": line}


def selected(items, side="design", body="Sun"):
    return next(
        item
        for item in line_fixings(items)
        if item["side"] == side and item["body"] == body
    )


def test_official_55_2_venus_in_harmonic_39_example():
    result = selected(
        {
            "design": [activation("Sun", 55, 2)],
            "personality": [activation("Venus", 39, 6)],
        }
    )
    assert result["status"] == "exaltation"
    assert result["fixing_planets"]["exaltation"] == [
        {
            "side": "personality",
            "body": "Venus",
            "gate": 39,
            "line": 6,
            "relation": "harmonic_gate",
            "calculation_path": "activations.personality.0",
        }
    ]


@pytest.mark.parametrize("line", [3, 4])
def test_official_16_mars_can_fix_other_lines_within_same_gate(line):
    result = selected(
        {
            "design": [activation("Sun", 16, line)],
            "personality": [activation("Mars", 16, 1)],
        }
    )
    assert result["status"] == "detriment"
    assert (
        result["fixing_planets"]["detriment"][0]["relation"] == "same_gate_other_line"
    )


def test_both_planet_polarities_are_retained_as_juxtaposition():
    result = selected(
        {
            "design": [activation("Sun", 27, 5), activation("Jupiter", 27, 1)],
            "personality": [activation("Saturn", 50, 6)],
        }
    )
    assert result["status"] == "juxtaposition"
    assert result["fixing_planets"]["exaltation"][0]["body"] == "Jupiter"
    assert result["fixing_planets"]["detriment"][0]["body"] == "Saturn"


def test_other_planets_and_nodes_cannot_substitute_for_named_fixing_planet():
    result = selected(
        {
            "design": [activation("Sun", 55, 2)],
            "personality": [activation("Mars", 39, 1), activation("NorthNode", 39, 1)],
        }
    )
    assert result["status"] == "unfixed"
    assert result["fixing_planets"] == {"exaltation": [], "detriment": []}


def test_all_five_official_jobs_fixing_arrows_without_adding_unshown_arrows():
    fixture = json.loads(
        (ROOT / "tests/fixtures/human-design-official-example.json").read_text()
    )
    sides = {
        side: [{"body": body, **value} for body, value in items.items()]
        for side, items in fixture["activations"].items()
    }
    fixed = {
        (a["side"], a["body"], a["status"])
        for a in line_fixings(sides)
        if a["status"] in {"exaltation", "detriment", "juxtaposition"}
    }
    # Independently visible triangles on the official chart, PDF7 / printed6.
    assert fixed == {
        ("design", "Sun", "detriment"),
        ("design", "Saturn", "exaltation"),
        ("design", "Uranus", "exaltation"),
        ("personality", "Moon", "exaltation"),
        ("personality", "Venus", "detriment"),
    }


def test_utc_leap_second_is_not_rebased_onto_next_midnight():
    midnight = _julian_day(datetime(2017, 1, 1, tzinfo=timezone.utc))
    leap_tt = midnight + (36 + 32.184 + 0.5) / 86400
    label, moment, is_leap = utc_from_tt(leap_tt)
    assert label.startswith("2016-12-31T23:59:60.") and is_leap
    assert moment is None
    label, moment, is_leap = utc_from_tt(midnight + (37 + 32.184) / 86400)
    assert label.startswith("2017-01-01T00:00:00") and not is_leap
    assert moment is not None


def test_design_root_can_lie_inside_an_actual_utc_leap_second():
    # Construct the birth through Swiss' independent crossing routine so that
    # its 88-degree earlier Sun occurs during the known inserted UTC second.
    leap_tt = (
        _julian_day(datetime(2017, 1, 1, tzinfo=timezone.utc))
        + (36 + 32.184 + 0.5) / 86400
    )
    target = (sun_at_tt(leap_tt) + 88) % 360
    birth_tt = runtime.ephemeris_call(
        "solcross", target, leap_tt + 70, runtime.swe.FLG_SWIEPH
    )
    chart = chart_at(datetime_from_tt(birth_tt))
    assert chart["design_utc"].startswith("2016-12-31T23:59:60.")
    assert chart["design_solver"]["utc_is_leap_second"] is True
    assert abs(chart["time_scales"]["design"]["jd_tt"] - leap_tt) * 86400 < 0.002
    assert chart["design_solver"]["bracket_width_seconds"] <= 0.0002


def test_every_frozen_positive_leap_second_and_its_adjacent_boundaries():
    count = 0
    for previous, current in zip(leap_table()["entries"], leap_table()["entries"][1:]):
        if current["tai_minus_utc_seconds"] - previous["tai_minus_utc_seconds"] != 1:
            continue
        effective = datetime.fromisoformat(current["effective_date"]).replace(
            tzinfo=timezone.utc
        )
        jd = _julian_day(effective)
        start = jd + (previous["tai_minus_utc_seconds"] + 32.184) / 86400
        stop = jd + (current["tai_minus_utc_seconds"] + 32.184) / 86400
        for moment in (start, start + 0.25 / 86400, start + 0.75 / 86400):
            label, date, leap = utc_from_tt(moment)
            assert leap and date is None and "T23:59:60." in label
        for moment in (start - 0.01 / 86400, stop, stop + 0.01 / 86400):
            _, date, leap = utc_from_tt(moment)
            assert not leap and date is not None
        count += 1
    assert count == 27


def test_tt_elapsed_days_do_not_lose_inserted_civil_second():
    chart = chart_at(datetime(2017, 3, 1, tzinfo=timezone.utc))
    solver = chart["design_solver"]
    assert (
        solver["days_before_birth"] - solver["civil_elapsed_days"]
    ) * 86400 == pytest.approx(1, abs=0.001)


def test_chart_utc_label_is_normalized_even_for_direct_library_call():
    from datetime import timedelta

    chart = chart_at(datetime(2000, 1, 1, 8, tzinfo=timezone(timedelta(hours=8))))
    assert chart["birth_utc"] == "2000-01-01T00:00:00+00:00"


@pytest.mark.parametrize(
    "longitude,line,candidates",
    [
        (145.27, 1, []),
        (145.35, 1, [2]),
        (145.4375, 2, []),
        (359.9, 2, []),
        (0.0, 2, []),
    ],
)
def test_source_conflict_is_located_only_where_it_changes_this_activation(
    longitude, line, candidates
):
    from fatebridge.core.human_design import longitude_activation

    # Source interval wrap-around is also checked near the end of the zodiac.
    coordinates = longitude_activation(longitude)
    assert coordinates["line"] == line
    report = source_activation_impacts(
        {"activations": {"personality": [{"body": "Sun", **coordinates}]}}
    )
    assert report["activations_checked"] == 1
    assert report["status"] == (
        "affected" if candidates else "no_line_discrepancy_at_returned_longitudes"
    )
    if candidates:
        assert report["differences"][0]["implemented_uniform_line"] == line
        assert report["differences"][0]["printed_line_candidates"] == candidates
        assert report["differences"][0]["source_pdf_page_one_based"] == 63
    else:
        assert report["differences"] == []


@pytest.fixture
def complete_run():
    return execute_tool(SPEC, SPEC.request_model(**example_input(SPEC)))


def test_fixed_reading_verifier_checks_all_eight_source_bound_statements(complete_run):
    result = verify_human_design_reading(complete_run)
    assert result["status"] == "verified_fixed_template_reading", result
    assert result["checked_statement_count"] == 10


@pytest.mark.parametrize(
    "tamper",
    [
        "text",
        "basis",
        "profile",
        "cross_gates",
        "fixing",
        "coordinates",
        "cross_source",
        "cross_order",
        "rule_trace",
        "ruleset",
        "gate_source",
        "source_consistency",
        "certification",
        "certification_type",
        "graph_boolean_type",
        "circuit_count",
        "circuit_label",
        "circuit_text",
        "variables_code",
        "variables_basis",
        "tone_orientation",
        "variable_certification",
    ],
)
def test_false_reading_or_internally_inconsistent_calculation_cannot_pass_even_after_rehash(
    complete_run, tamper
):
    changed = deepcopy(complete_run)
    if tamper == "text":
        changed["interpretation"]["authority_meaning"] = "头脑是可靠的内在权威。"
    elif tamper == "basis":
        changed["interpretation"]["statements"][0]["basis"][0]["value"] = "reflector"
    elif tamper == "profile":
        changed["profile"] = "6/3"
    elif tamper == "cross_gates":
        changed["incarnation_cross"]["gates"][0] = 1
    elif tamper == "fixing":
        changed["depth_evidence"]["line_fixings"][0]["status"] = "invented"
    elif tamper == "cross_source":
        changed["incarnation_cross"]["source_pdf_page_one_based"] = 1
    elif tamper == "cross_order":
        changed["incarnation_cross"]["order"].reverse()
    elif tamper == "rule_trace":
        changed["rule_trace"][0]["result"]["target_solar_arc_degrees"] = 90
    elif tamper == "ruleset":
        changed["rulesets"][0]["author"] = "Invented certification authority"
    elif tamper == "gate_source":
        changed["gate_evidence"][0]["source_center"] = "Invented center"
    elif tamper == "source_consistency":
        changed["source_consistency"]["discrepancies"] = []
    elif tamper == "certification":
        changed["validation"].update(
            all_three_axes_full_marks=True,
            all_four_axes_full_marks=True,
            authority_certified=True,
            prediction="proven",
        )
    elif tamper == "certification_type":
        changed["validation"]["authority_certified"] = 0
    elif tamper == "graph_boolean_type":
        changed["bodygraph"]["motor_to_throat"] = int(
            changed["bodygraph"]["motor_to_throat"]
        )
    elif tamper == "circuit_count":
        changed["bodygraph"]["circuitry"]["group_channel_counts"]["individual"] += 1
    elif tamper == "circuit_label":
        changed["bodygraph"]["channels"][0]["circuit"] = "invented"
    elif tamper == "circuit_text":
        changed["interpretation"][
            "circuitry_meaning"
        ] = "通道数量证明你具备主导人格和预测能力。"
    elif tamper == "variables_code":
        changed["variables"]["code"] = (
            "PRR DRR" if changed["variables"]["code"] != "PRR DRR" else "PLL DLL"
        )
    elif tamper == "variables_basis":
        changed["variables"]["arrows"][0]["basis"][0]["value"] = True
    elif tamper == "tone_orientation":
        row = changed["activations"]["personality"][0]
        row["tone_orientation"] = (
            "right" if row["tone_orientation"] == "left" else "left"
        )
    elif tamper == "variable_certification":
        changed["variables"]["subdivision_accuracy_certified"] = True
    else:
        changed["activations"]["personality"][0]["gate"] = 1
    changed["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in changed.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(changed)["status"] == "rejected"


def test_projection_is_not_complete_run_verification(complete_run):
    assert (
        verify_human_design_reading(
            {
                "interpretation": complete_run["interpretation"],
                "run_metadata": complete_run["run_metadata"],
            }
        )["status"]
        == "rejected"
    )


@pytest.mark.parametrize(
    "root,bad",
    [
        ("bodygraph", "wrong"),
        ("interpretation", []),
        ("activations", None),
        ("incarnation_cross", True),
        ("run_metadata", None),
    ],
)
def test_malformed_result_is_rejected_without_verifier_crash(complete_run, root, bad):
    value = deepcopy(complete_run)
    value[root] = bad
    assert verify_human_design_reading(value)["status"] == "rejected"


def test_astronomy_audit_replays_current_solver_not_only_the_frozen_reference(
    monkeypatch,
):
    from scripts import audit_human_design as audit

    original = audit.solve_design_epoch

    def wrong_root(*args, **kwargs):
        result = original(*args, **kwargs)
        result["time"]["jd_tt"] += 1
        return result

    monkeypatch.setattr(audit, "solve_design_epoch", wrong_root)
    report = audit.astronomy_checks()
    assert all(row["within_tolerance"] for row in report["solar_arcs"])
    assert not all(row["current_root_within_tolerance"] for row in report["solar_arcs"])
    assert report["status"] == "failed"
