"""Unchanged official glyphs, node recipients and complete mechanism readings."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_depth import line_fixings
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_fixing import fixing_marker_checks

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1971,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
)


def test_all_unchanged_official_fixing_slots_preserve_visible_and_unobservable_states():
    report = fixing_marker_checks(ROOT)
    assert report["case_count"] == 19
    assert report["activation_slots_observed"] == 494
    assert (
        report["visible_polarities_matched"] == report["visible_polarity_count"] == 138
    )
    assert report["visible_polarity_counts"] == {"detriment": 69, "exaltation": 69}
    assert report["visible_node_recipient_count"] == 11
    assert report["visible_unitary_recipient_count"] == 2
    assert report["rendered_projection_matches"] == 494
    assert report["blank_slot_count"] == 356
    assert report["mismatches"] == []
    assert report["complete_fixing_statuses_certified"] is False
    assert report["full_384_line_meaning_acceptance"] is False
    # Do not relabel blank juxtaposition glyphs as independently observed unfixed.
    assert any(
        r["computed_fixing_state"] == "juxtaposition"
        and r["observed_marker"] == "no_visible_marker"
        for r in report["cases"]
    )


def test_original_failing_observations_are_retained_including_all_13_gaps():
    before = json.loads(
        (ROOT / "docs/validation/human-design-fixing-before.json").read_text()
    )
    # The pre-change comparison saved all visible glyphs, not blank slots.
    assert len(before) == 138
    visible = [r for r in before if r["visible_marker"] != "no_visible_marker"]
    gaps = [r for r in visible if r["engine_status"] != r["visible_marker"]]
    assert len(visible) == 138
    assert len(gaps) == 13
    assert sum(r["body"] in {"NorthNode", "SouthNode"} for r in gaps) == 11
    assert sum(r["polarity_kind"] == "unitary" for r in gaps) == 2
    ref = json.loads(
        (
            ROOT / "src/fatebridge/data/human_design/fixing-2026-reference.json"
        ).read_text()
    )
    assert (
        ref["plan_sha256"]
        == hashlib.sha256(
            (
                ROOT / "tests/fixtures/human-design-fixing-observation-plan.json"
            ).read_bytes()
        ).hexdigest()
    )
    for source in ref["cohort_sources"]:
        assert (
            hashlib.sha256(
                (ROOT / "tests/fixtures" / source["fixture"]).read_bytes()
            ).hexdigest()
            == source["sha256"]
        )


def test_a_node_can_receive_the_harmonic_planet_fixing_but_cannot_fix_other_lines():
    records = line_fixings(
        {
            "design": [
                {"body": "NorthNode", "gate": 55, "line": 2},
                {"body": "Sun", "gate": 55, "line": 2},
            ],
            "personality": [
                {"body": "Earth", "gate": 39, "line": 1},
                {"body": "SouthNode", "gate": 39, "line": 1},
            ],
        }
    )
    node = next(
        r for r in records if r["side"] == "design" and r["body"] == "NorthNode"
    )
    assert node["calculation_path"] == "activations.design.0"
    assert node["fixing_state"] == node["status"] == "detriment"
    assert node["recipient_kind"] == "node_activation"
    assert node["fixing_planets"]["detriment"] == [
        {
            "side": "personality",
            "body": "Earth",
            "gate": 39,
            "line": 1,
            "relation": "harmonic_gate",
            "calculation_path": "activations.personality.0",
        }
    ]
    assert "交点位置可接受固定" in node["reading"]
    assert "人格地球 39.1" in node["reading"]
    assert all(
        t["body"] not in {"NorthNode", "SouthNode"}
        for r in records
        for ts in r["fixing_planets"].values()
        for t in ts
    )
    without_earth = line_fixings(
        {
            "design": [{"body": "Sun", "gate": 55, "line": 2}],
            "personality": [{"body": "SouthNode", "gate": 39, "line": 1}],
        }
    )
    recipient = next(
        r for r in without_earth if r["side"] == "design" and r["body"] == "Sun"
    )
    assert recipient["calculation_path"] == "activations.design.0"
    assert recipient["fixing_state"] == "unfixed"


@pytest.mark.parametrize("triggered", [False, True])
def test_unitary_source_category_does_not_invent_an_active_fixing(triggered):
    sides = {
        "design": [{"body": "Venus", "gate": 57, "line": 3}],
        "personality": [{"body": "Mercury", "gate": 57 if triggered else 1, "line": 2}],
    }
    value = next(
        r for r in line_fixings(sides) if r["side"] == "design" and r["body"] == "Venus"
    )
    assert value["calculation_path"] == "activations.design.0"
    assert value["status"] == "unitary_polarity"
    assert value["polarity_kind"] == "unitary"
    assert value["fixing_state"] == ("exaltation" if triggered else "unfixed")
    assert value["detriment_planet"] is None
    assert "须另查本盘是否实际触发" in value["reading"]
    assert ("本盘触发上升极性" in value["reading"]) is triggered


def test_no_planet_polarity_has_no_invented_trigger_or_full_line_meaning():
    value = line_fixings({"design": [{"body": "Sun", "gate": 54, "line": 4}]})[0]
    assert value["fixing_state"] == "not_applicable_no_planet_polarity"
    assert value["fixing_planets"] == {"exaltation": [], "detriment": []}
    assert "不补造固定极性" in value["reading"]
    assert "未提供该线完整原典线义" in value["reading"]


@pytest.fixture(scope="module")
def complete():
    return execute_tool(SPEC, SPEC.request_model(**INPUT))


def test_all_26_mechanism_readings_are_checked_without_claiming_full_line_acceptance(
    complete,
):
    depth = complete["depth_evidence"]
    assert len(depth["line_fixings"]) == 26
    assert all(r["reading"] for r in depth["line_fixings"])
    assert sum(depth["fixing_summary"]["fixing_state_counts"].values()) == 26
    assert depth["fixing_summary"]["node_recipient_count"] == 4
    assert depth["fixing_summary"]["complete_line_meanings_accepted"] is False
    assert depth["fixing_policy"]["node_donor_exclusion_author"] == "Martin Grassinger"
    assert depth["fixing_policy"]["node_donor_exclusion_pdf_page_one_based"] == 2
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_fixing_reading_count"] == 26
    assert check["checked_statement_count"] == 10  # All prior statements retained.
    assert complete["validation"]["all_three_axes_full_marks"] is False


@pytest.mark.parametrize(
    "tamper",
    [
        "reading",
        "state",
        "recipient",
        "trigger",
        "summary",
        "policy",
        "author",
        "meaning",
        "omit",
        "certificate",
    ],
)
def test_forged_fixing_mechanism_cannot_pass_even_after_rehash(complete, tamper):
    value = deepcopy(complete)
    depth = value["depth_evidence"]
    row = next(
        r
        for r in depth["line_fixings"]
        if r["fixing_state"] == "detriment" and r["body"] == "NorthNode"
    )
    if tamper == "reading":
        row["reading"] = "下降极性表示现实失败。"
    elif tamper == "state":
        row["fixing_state"] = "unfixed"
    elif tamper == "recipient":
        row["recipient_kind"] = "planet_activation"
    elif tamper == "trigger":
        row["fixing_planets"]["detriment"][0]["body"] = "NorthNode"
    elif tamper == "summary":
        depth["fixing_summary"]["activation_count"] = 25
    elif tamper == "policy":
        depth["fixing_policy"]["node_donors_allowed"] = True
    elif tamper == "author":
        depth["fixing_policy"]["node_donor_exclusion_author"] = "Ra Uru Hu"
    elif tamper == "meaning":
        value["interpretation"]["line_fixing_meaning"] = "全部384线义已认证。"
    elif tamper == "omit":
        depth["line_fixings"].pop()
    else:
        depth["fixing_summary"]["complete_line_meanings_accepted"] = True
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    check = verify_human_design_reading(value)
    assert check["status"] == "rejected", check
