"""Frozen source and independent directed geometry; no real traveler observations."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.meihua_traveler import traveler_qualifications, traveler_ruleset
from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parent / "fixtures/meihua_traveler_v1"
PROFILE = json.loads((FIXTURE / "profile.json").read_text())
GEOMETRY = json.loads((FIXTURE / "geometry384-selected-mutual-policy.json").read_text())


def calculate(code, line, branch=None):
    return calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": code, "moving_line": line},
        interpretation_topic="traveler",
        season_month_branch=branch,
    )


def resolve(result, path):
    for key in path.split("."):
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def test_frozen_source_and_reference_error_are_both_retained():
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_text())
    assert not freeze["new_production_module_present"]
    assert not freeze["new_profile_present"]
    for name, digest in freeze["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    amendment = json.loads((FIXTURE / "geometry-amendment.json").read_text())
    assert len(amendment["changed_geometry_rows"]) == 8
    assert (
        hashlib.sha256(
            (FIXTURE / "geometry384-selected-mutual-policy.json").read_bytes()
        ).hexdigest()
        == amendment["amended_sha256"]
    )
    assert traveler_ruleset() == PROFILE
    altered = traveler_ruleset()
    altered["rules"][0]["quote"] = "modified"
    assert traveler_ruleset() == PROFILE
    assert PROFILE["supplement_header"]["quote"] == "又以用卦為行人之盈旺"
    assert (
        PROFILE["supplement_header"]["comparison_quote"] == "又以用卦看行人在外之情況"
    )
    assert PROFILE["supplement_rules"][-1]["quote"] == "兌主紛爭之應"
    assert PROFILE["supplement_rules"][-1]["comparison_quote"] == "兌主紛爭"


def expected_strength(element, branch):
    if branch is None:
        return None
    strong, weak = (
        ("土", "水")
        if branch in "辰戌丑未"
        else (
            ("木", "土")
            if branch in "寅卯"
            else (
                ("火", "金")
                if branch in "巳午"
                else ("金", "木") if branch in "申酉" else ("水", "火")
            )
        )
    )
    return "旺" if element == strong else "衰" if element == weak else "原文未定"


@pytest.mark.parametrize("case", GEOMETRY, ids=lambda c: f"{c['code']}:{c['line']}")
@pytest.mark.parametrize("branch", [None, *"子丑寅卯辰巳午未申酉戌亥"])
def test_all_geometries_bind_their_own_initial_use_and_directed_actors(case, branch):
    result = calculate(case["code"], case["line"], branch)
    clause = result["interpretation"]["topic_reading"]
    q = clause["chapter_qualifications"]
    frame = q["initial_use_frame"]
    assert (clause["body"], clause["use"], frame["target_trigram"]) == (
        case["body"],
        case["use"],
        case["use"],
    )
    expected = next(r for r in PROFILE["rules"] if r["relation"] == clause["relation"])
    assert clause["quote"] == expected["quote"]
    assert resolve(result, frame["target_fact_path"])["name"] == case["use"]
    assert (
        resolve(result, q["original_body_frame"]["initial_relation_fact_path"])
        == clause["relation"]
    )
    for actor, reference in zip(frame["actors"], case["actors"], strict=True):
        assert (
            actor["role"],
            actor["trigram"],
            actor["element"],
            actor["relation_to_initial_use"],
            actor["controlled_by_roles"],
        ) == (
            reference["role"],
            reference["trigram"],
            reference["element"],
            reference["relation_to_use"],
            reference["controlled_by_roles"],
        )
        assert resolve(result, actor["fact_path"])["name"] == actor["trigram"]
        assert resolve(result, actor["target_fact_path"])["name"] == case["use"]
    generation = [
        r["role"]
        for r in case["actors"]
        if r["relation_to_use"] == "actor_generates_target"
    ]
    received = q["received_generation"]
    assert received["actor_roles"] == generation
    assert received["selected_scope_condition"] is bool(generation)
    assert received["full_clause_condition"] is None
    assert received["net_support_established"] is False
    strength = expected_strength(frame["target_element"], branch)
    assert frame["actual_strength"] == strength
    assert (
        frame["strength_fact_path"] is None
        if branch is None
        else resolve(result, frame["strength_fact_path"]) == strength
    )
    weak = True if strength == "衰" else False if strength == "旺" else None
    controlled = bool(case["use_controlled_by"])
    wc = q["weak_and_controlled"]
    assert wc["actor_roles"] == case["use_controlled_by"]
    assert wc["use_weak"] is weak
    assert wc["use_controlled_in_selected_scope"] is controlled
    assert wc["selected_scope_condition"] is (
        False if weak is False or not controlled else True if weak is True else None
    )
    assert wc["full_clause_condition"] is None
    assert len(q["many_clauses"]) == 2 and len(q["initial_use_symbols"]) == 2
    for row in q["many_clauses"]:
        assert (
            row["threshold"]
            is row["selected_scope_condition"]
            is row["full_clause_condition"]
            is None
        )
    for row in q["initial_use_symbols"]:
        assert row["selected_scope_condition"] is (row["trigram"] == case["use"])
        assert resolve(result, row["trigram_fact_path"]) == case["use"]
        assert row["full_clause_condition"] is None
    assert all(
        q[k] is None
        for k in (
            "event_time",
            "return_verified",
            "real_location",
            "hazard_verdict",
            "success_probability",
            "real_outcome",
        )
    )
    assert not q["selection_policy"]["unique_classical_scope_adjudicated"]
    assert not frame["recursive_cancellation_applied"]
    assert not frame["external_observations_rebased_to_use"]
    assert q["summary"] in result["summary"]


def test_body_generates_use_is_receipt_by_use_without_reversing_original_body():
    result = calculate("101001", 4, "寅")
    q = result["interpretation"]["topic_reading"]["chapter_qualifications"]
    assert result["meihua"]["body_use_relation"] == "体生用"
    assert q["original_body_frame"]["initial_relation"] == "体生用"
    actor = next(a for a in q["initial_use_frame"]["actors"] if a["role"] == "body")
    assert actor["relation_to_initial_use"] == "actor_generates_target"
    assert "body" in q["received_generation"]["actor_roles"]
    reverse = calculate("101001", 1, "寅")
    rq = reverse["interpretation"]["topic_reading"]["chapter_qualifications"]
    assert reverse["meihua"]["body_use_relation"] == "用生体"
    assert (
        next(a for a in rq["initial_use_frame"]["actors"] if a["role"] == "body")[
            "relation_to_initial_use"
        ]
        == "target_generates_actor"
    )
    assert "body" not in rq["received_generation"]["actor_roles"]


def test_use_strength_and_control_must_both_hold_not_body_strength():
    summer = calculate("110101", 1, "巳")
    q = summer["interpretation"]["topic_reading"]["chapter_qualifications"]
    assert summer["meihua"]["seasonal_strength"]["trigrams"][0]["strength"] == "旺"
    assert q["initial_use_frame"]["actual_strength"] == "衰"
    assert q["weak_and_controlled"]["selected_scope_condition"] is True
    unknown = calculate("110101", 1)
    uq = unknown["interpretation"]["topic_reading"]["chapter_qualifications"]
    assert uq["weak_and_controlled"]["selected_scope_condition"] is None
    assert uq["weak_and_controlled"]["real_hazard_verdict"] is None


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_each_count_candidate_keeps_own_target_strength_paths_and_qualifications(basis):
    r = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
            "line_sum_basis": basis,
        },
        interpretation_topic="traveler",
        season_month_branch="巳",
    )
    rows = r["interpretation"]["casting_readings"]
    assert {
        row["topic_clause"]["chapter_qualifications"]["initial_use_frame"][
            "target_trigram"
        ]
        for row in rows
    } == {"乾", "离"}
    for i, row in enumerate(rows):
        q = row["topic_clause"]["chapter_qualifications"]
        frame = q["initial_use_frame"]
        assert frame["target_fact_path"] == f"meihua.counting_variants.{i}.use_trigram"
        assert resolve(r, frame["strength_fact_path"]) == frame["actual_strength"]
        assert q["summary"] in r["summary"]
        for actor in frame["actors"]:
            assert resolve(r, actor["fact_path"])["name"] == actor["trigram"]
    selected = next(row for row in rows if row["selected"])
    assert (
        selected["topic_clause"]["chapter_qualifications"]["initial_use_frame"][
            "target_trigram"
        ]
        == r["meihua"]["use_trigram"]["name"]
    )


def test_mismatched_target_or_strength_is_rejected_instead_of_borrowing():
    r = calculate("110101", 1, "巳")
    cast = r["meihua"]
    for changed in ("target", "strength"):
        stages = deepcopy(cast["stage_relations"])
        strength = deepcopy(cast["seasonal_strength"])
        if changed == "target":
            stages[0]["fact_path"] = "meihua.changed_hexagram.lower"
        else:
            strength["trigrams"][1]["trigram"] = cast["body_trigram"]["name"]
        with pytest.raises(ValueError, match="Traveler"):
            traveler_qualifications(
                cast,
                stages,
                strength,
                fact_prefix="meihua",
                strength_prefix="meihua.seasonal_strength",
            )


def test_question_keywords_do_not_select_new_chapter_or_infer_real_whereabouts():
    options = MeihuaInterpretationOptions(interpretation_topic="traveler")
    assert options.interpretation_topic == "traveler"
    r = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "111111", "moving_line": 1},
        question="行人已经返归，测试文字不得触发分支",
    )
    assert r["interpretation"]["interpretation_topic"] == "general"
