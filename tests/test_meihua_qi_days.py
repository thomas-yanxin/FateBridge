"""Literal day-branch atoms and chapter roles, not event-date forecasts."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.meihua_qi_days import _reading, qi_day_atom_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parent / "fixtures/meihua_qi_days_v1"
PROFILE = json.loads((FIXTURE / "profile.json").read_text())
GEOMETRY = json.loads((FIXTURE / "geometry384.json").read_text())
TRUTH = {
    (r["trigram"], r["day_branch"]): r["literal_named_day_branch_atom_met"]
    for r in json.loads((FIXTURE / "day-atoms96.json").read_text())
}


def resolve(result, path):
    for key in path.split("."):
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def calculate(case, topic, branch):
    args = {
        "casting": {
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        "interpretation_topic": topic,
    }
    if branch is not None:
        args["day_qi_context"] = {
            "label": "合成日支原子核对，非现实观测",
            "day_branch": branch,
        }
    return calculate_meihua_cast(**args)


def expected_targets(case, topic):
    support = [r for r in case["rows"] if r["relation"] == "用生体"]
    attack = [r for r in case["rows"] if r["relation"] == "用克体"]
    if topic == "wealth":
        return [
            ("wealth_gain", r["role"], r["trigram"], r["relation"], True)
            for r in support
        ] + [
            ("wealth_loss", r["role"], r["trigram"], r["relation"], True)
            for r in attack
        ]
    return (
        [
            ("reputation_completion", r["role"], r["trigram"], r["relation"], True)
            for r in support
        ]
        + [
            ("reputation_office", r["role"], r["trigram"], r["relation"], None)
            for r in attack
        ]
        + (
            []
            if attack
            else [
                (
                    "reputation_body_without_attacker",
                    "body",
                    case["body"],
                    "body_self",
                    None,
                )
            ]
        )
    )


def test_source_and_all_96_literal_memberships_were_frozen_before_new_production():
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_text())
    assert (
        not freeze["new_production_module_present"]
        and not freeze["new_profile_present"]
    )
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert len(TRUTH) == 96
    assert qi_day_atom_ruleset() == PROFILE
    changed = qi_day_atom_ruleset()
    changed["literal_day_branch_atoms"]["坤"]["day_branches"] = ["辰"]
    assert qi_day_atom_ruleset() == PROFILE


@pytest.mark.parametrize("case", GEOMETRY, ids=lambda c: f"{c['code']}:{c['line']}")
@pytest.mark.parametrize("topic", ["wealth", "reputation"])
@pytest.mark.parametrize("branch", [None, *"子丑寅卯辰巳午未申酉戌亥"])
def test_all_9984_role_day_contexts_use_actual_selector_and_literal_membership(
    case, topic, branch
):
    result = calculate(case, topic, branch)
    assert "error" not in result
    clause = result["interpretation"]["topic_reading"]
    if branch is None:
        assert "qi_day_timing_reference" not in clause
        return
    q = clause["qi_day_timing_reference"]
    rows = q["source_selected_role_references"]
    assert [
        (
            r["selector_id"],
            r["role"],
            r["trigram"],
            r["relation_to_original_body"],
            r["selected_source_context_condition"],
        )
        for r in rows
    ] == expected_targets(case, topic)
    for row in rows:
        assert resolve(result, row["trigram_fact_path"]) == row["trigram"]
        match = row["input_day_matches"][0]
        assert resolve(result, match["day_branch_fact_path"]) == branch
        assert (
            match["literal_named_day_branch_atom_met"]
            is TRUTH[(row["trigram"], branch)]
        )
        assert match["full_source_timing_condition"] is match["real_outcome"] is None
        assert len(row["input_day_matches"]) == 1
        assert row["boundary_changes_literal_atom_match"] is False
        assert row["countercontrol_and_strength_combined_into_timing"] is False
    assert all(
        q[k] is None
        for k in [
            "candidate_event_dates",
            "event_time",
            "real_world_observation_window",
            "real_outcome",
        ]
    )
    assert not q["literal_branch_membership_is_element_strength"]
    assert not q["nonmembership_negates_full_source_condition"]
    assert not q["next_or_nearest_matching_day_selected"]
    assert not q["role_occurrences_are_independent_observations"]
    assert q["independent_verified_observations"] == 0
    assert q["summary"] in result["summary"]
    assert result["interpretation"]["traditional_judgement"].endswith(
        q["summary"] + clause["qi_branch_timing_reference"]["summary"]
    )


@pytest.mark.parametrize(
    "branch,expected",
    [("辰", False), ("戌", False), ("丑", False), ("未", True), ("申", True)],
)
def test_kun_month_only_labels_are_not_day_labels_or_element_strength(branch, expected):
    result = calculate({"code": "000111", "line": 1}, "wealth", branch)
    q = result["interpretation"]["topic_reading"]["qi_day_timing_reference"]
    row = next(r for r in q["source_selected_role_references"] if r["role"] == "use")
    assert row["trigram"] == "坤"
    assert row["literal_day_branch_atom"]["day_branches"] == ["未", "申"]
    assert row["literal_day_branch_atom"][
        "explicit_month_only_spans_excluded_from_day_match"
    ] == ["辰戌丑未月"]
    assert row["input_day_matches"][0]["literal_named_day_branch_atom_met"] is expected
    assert row["input_day_matches"][0]["full_source_timing_condition"] is None


@pytest.mark.parametrize("office", [None, False, True])
@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_count_candidates_keep_own_roles_paths_and_office_context(office, basis):
    args = {
        "casting": {
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
            "line_sum_basis": basis,
        },
        "interpretation_topic": "reputation",
        "day_qi_context": {"label": "合成午日，不推定在任", "day_branch": "午"},
    }
    if office is not None:
        args["reputation_context"] = {
            "label": "合成原文在任声明",
            "currently_in_office": office,
        }
    result = calculate_meihua_cast(**args)
    for i, candidate in enumerate(result["interpretation"]["casting_readings"]):
        q = candidate["topic_clause"]["qi_day_timing_reference"]
        for row in q["source_selected_role_references"]:
            assert row["trigram_fact_path"].startswith(f"meihua.counting_variants.{i}.")
            assert resolve(result, row["trigram_fact_path"]) == row["trigram"]
            assert (
                resolve(result, row["input_day_matches"][0]["day_branch_fact_path"])
                == "午"
            )
            if row["selector_id"] == "reputation_office":
                assert row["selected_source_context_condition"] is office
        assert candidate["traditional_judgement"].endswith(
            q["summary"]
            + candidate["topic_clause"]["qi_branch_timing_reference"]["summary"]
        )
        assert q["summary"] in result["summary"]


@pytest.mark.parametrize("topic", ["wealth", "reputation"])
def test_23h_retains_midnight_and_zi_start_labels_without_selecting_a_forecast(topic):
    result = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=27,
        analysis_hour=23,
        analysis_timezone="Asia/Shanghai",
        interpretation_topic=topic,
    )
    q = result["interpretation"]["topic_reading"]["qi_day_timing_reference"]
    assert [r["id"] for r in q["input_calendar_labels"]] == [
        "local_midnight",
        "zi_start",
    ]
    assert [r["selected_input_day_label"] for r in q["input_calendar_labels"]] == [
        True,
        False,
    ]
    for row in q["source_selected_role_references"]:
        assert [r["calendar_id"] for r in row["input_day_matches"]] == [
            "local_midnight",
            "zi_start",
        ]
        for record in row["input_day_matches"]:
            assert (
                resolve(result, record["day_branch_fact_path"]) == record["day_branch"]
            )
            assert (
                record["literal_named_day_branch_atom_met"]
                is TRUTH[(row["trigram"], record["day_branch"])]
            )
        assert row["boundary_changes_literal_atom_match"] == (
            len(
                {
                    r["literal_named_day_branch_atom_met"]
                    for r in row["input_day_matches"]
                }
            )
            > 1
        )
    assert q["candidate_event_dates"] is q["event_time"] is None


def test_body_no_attacker_reference_keeps_full_absence_unknown():
    result = calculate({"code": "111111", "line": 1}, "reputation", "戌")
    q = result["interpretation"]["topic_reading"]["qi_day_timing_reference"]
    body = next(r for r in q["source_selected_role_references"] if r["role"] == "body")
    assert body["trigram"] == "乾" and body["selected_source_context_condition"] is None
    assert body["input_day_matches"][0]["literal_named_day_branch_atom_met"] is True
    assert body["input_day_matches"][0]["full_source_timing_condition"] is None


@pytest.mark.parametrize("fault", ["day_role", "drop_selector"])
def test_borrowed_role_or_incomplete_source_selector_is_rejected(fault):
    result = calculate({"code": "000111", "line": 1}, "reputation", "未")
    layer = deepcopy(result["interpretation"])
    if fault == "day_role":
        layer["day_qi"]["calendar_candidates"][0]["roles"][0]["trigram"] = "离"
    else:
        layer["topic_reading"]["chapter_qualifications"]["support_time_references"] = []
    with pytest.raises(ValueError, match="Qi"):
        _reading(
            result["meihua"],
            layer,
            "reputation",
            fact_prefix="meihua",
            layer_path="interpretation",
            clause_path="interpretation.topic_reading",
        )
