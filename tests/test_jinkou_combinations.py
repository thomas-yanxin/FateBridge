"""Literal trine clauses, actual conditions and unresolved transformation."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.jinkou_combinations import trine_evidence
from fatebridge.core.output_chinese import JinkouCombinations
from fatebridge.services.metaphysics import _build_jinkou_snapshot_text
from tests.test_ren_classical_depth import AUDIT as V1

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_jinkou_combinations", ROOT / "scripts/audit_jinkou_combinations.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def by_phase(result, phase):
    return next(r for r in result["trines"] if r["element"] == phase)


def test_all_frozen_clauses_and_full_branch_space_keep_old_disagreements():
    result = AUDIT.audit()
    assert result["primary_stem_clause_count"] == 12
    assert result["primary_waiting_clause_count"] == 4
    assert result["synthetic_matrix_count"] == 6912
    assert result["synthetic_matrix_classifications"]["branches_complete"] == 24
    assert result["synthetic_matrix_failures"] == []
    assert result["selected_checks_passed"]
    assert result["classical_acceptance_passed"] is False
    assert result["goal_complete"] is False
    prior = result["prior_64_case_comparison"]
    assert prior["matched_semantic_cases"] == 54
    assert prior["matched_source_day_cases"] == 46
    assert len(prior["semantic_failures"]) == 4
    assert prior["unevaluated_definitions"] == 6


def test_printed_p01_reconstruction_keeps_distinct_clash_break_and_empty_facts():
    # P01's symbolic month/day/hour; not an inferred Gregorian date.
    board = V1.observe_jinkou(
        dict(day="甲辰", hour="申", ground="午", general="子", month="子")
    )
    assert [r["content"] for r in board["rows"]] == ["庚", "寅", "戌", "午"]
    row = by_phase(board["combinations"], "火")
    assert row["structural_status"] == "branches_complete_requires_adjudication"
    assert row["human_stem_relation"] == "局克人元"
    facts = {r["position"]: r for r in row["member_conditions"]}
    assert facts["贵神"]["xun_kong"] is True
    assert facts["将神"]["day_clash"] is True
    assert facts["地分"]["month_break"] is True
    assert row["transformation_confirmed"] is None
    assert row["du_he"] is None
    assert row["waiting_branch"] is None
    assert row["calendar_candidates"] is None
    assert board["use_evidence"]["comprehensive_position"] is None
    assert (
        board["overview"]["use_position"] == board["use_evidence"]["polarity_position"]
    )


@pytest.mark.parametrize(
    "phase,branches,self_listed", [("水", "申子辰", "辰"), ("金", "巳酉丑", "巳")]
)
def test_trine_member_in_disruptor_list_is_not_automatically_a_broken_trine(
    phase, branches, self_listed
):
    result = trine_evidence(
        AUDIT.symbolic_rows("甲", list(branches)), day_branch="卯", month_branch="丑"
    )
    row = by_phase(result, phase)
    assert (
        self_listed in row["branches"]
        and self_listed in row["source_listed_disruptors"]
    )
    assert row["structural_status"] == "branches_complete_requires_adjudication"
    assert row["disruptor_application"] == "context_unadjudicated_not_presence_rule"
    assert row["transformation_confirmed"] is None


def test_two_distinct_water_members_wait_for_chen_with_scan_name_retained():
    row = by_phase(
        trine_evidence(
            AUDIT.symbolic_rows("甲", list("申子申")),
            day_branch="子",
            month_branch="寅",
        ),
        "水",
    )
    assert row["partial_name"] == "润下破体课"
    assert row["present_branches"] == ["申", "子"]
    assert row["waiting_branch"] == "辰"
    assert row["structural_status"] == "missing_one_requires_adjudication"
    assert row["calendar_candidates"] is None


def test_no_candidate_trine_does_not_create_a_hypothetical_control_judgment():
    board = V1.observe_jinkou(dict(day="戊辰", hour="申", ground="酉", general="子"))
    row = by_phase(board["combinations"], "火")
    assert row["structural_status"] == "insufficient_members"
    assert row["human_stem_relation"] is None
    assert row["controlling_dun_stems"] == []
    assert "未比较人元与局" in row["basis"]


def test_fire_clause_uses_general_dun_stem_not_its_intrinsic_earth_phase():
    # Synthetic standard-method chart; no original event or predicted outcome.
    board = V1.observe_jinkou(
        dict(day="戊辰", hour="申", ground="午", general="子", month="子")
    )
    row = by_phase(board["combinations"], "火")
    assert row["structural_status"] == "branches_complete_requires_adjudication"
    assert board["rows"][2]["content"] == "戌" and board["rows"][2]["element"] == "土"
    assert row["controlling_dun_stems"] == [
        {
            "position": "将神",
            "stem": "壬",
            "element": "水",
            "trine_element": "火",
            "explicit_fire_clause": True,
        }
    ]
    assert row["transformation_confirmed"] is None


@pytest.mark.parametrize("day", ["甲辰", "戊辰"])
def test_snapshot_renders_positive_conditions_without_promoting_them_to_a_verdict(day):
    case = dict(day=day, hour="申", ground="午", general="子", month="子")
    board = V1.observe_jinkou(case)
    seed = V1.make_seed(case)
    seed.calendar_context["next_solar_term"] = {"name": "小寒"}
    text = _build_jinkou_snapshot_text(seed=seed, jinkou=board)
    row = by_phase(board["combinations"], "火")
    assert "[三合与虚一待用]" in text and row["basis"] in text
    assert "日冲" in text and "月破" in text and "旬空" in text
    assert board["combinations"]["scope"] in text
    if day == "戊辰":
        assert "将神遁干壬水克火局" in text
        assert "符合本节壬癸克火局条件" in text


@pytest.mark.parametrize(
    "field,value",
    [
        ("transformation_confirmed", True),
        ("du_he", False),
        ("calendar_candidates", ["2026-10-22"]),
    ],
)
def test_public_schema_cannot_turn_unadjudicated_layers_into_assertions(field, value):
    with pytest.raises(ValidationError):
        JinkouCombinations.model_validate({"trines": [{field: value}]})


def test_reference_mutation_cannot_redefine_the_acceptance_labels(tmp_path):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, target)
    path = target / "reference.json"
    ref = json.loads(path.read_text())
    ref["waiting_examples"][1]["name"] = "炎上破体课"
    path.write_text(json.dumps(ref, ensure_ascii=False))
    with pytest.raises(ValueError, match="reference changed"):
        AUDIT.reference(target)


@pytest.mark.parametrize("day", ["甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅"])
def test_literal_case_auxiliary_emptiness_obeys_original_frozen_xun_table(day):
    patterns = AUDIT.load_script("audit_jinkou_patterns")
    rules = V1.load_frozen_corpus()["rules"]
    label = rules["empty"][day]
    phase = label[0] if label != "无四大空亡" else None
    for stem in "甲丙戊庚壬":
        case = {"day": day, "positions": [stem, "玄武", "酉", "寅"]}
        for row in patterns.literal_rows(case, rules["inherent"]):
            assert row["si_da_kong"] == (row["element"] == phase)
