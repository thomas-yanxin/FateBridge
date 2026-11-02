"""Independent construction checks retain incompatible literal source rows."""

import copy
import hashlib
import json
import shutil

import pytest

from scripts.audit_jinkou_construction_diagnosis import (
    CORPUS,
    audit,
    god_map,
    reference,
)


@pytest.mark.parametrize(
    "fault", ["data", "manifest", "extra", "missing", "joint_rewrite"]
)
def test_independent_rule_and_source_identity_cannot_be_rewritten(fault, tmp_path):
    target = tmp_path / "ref"
    shutil.copytree(CORPUS, target)
    p = target / "reference.json"
    if fault in {"data", "joint_rewrite"}:
        v = json.loads(p.read_text())
        v["day_starts"]["庚"] = "未"
        p.write_text(json.dumps(v))
        if fault == "joint_rewrite":
            m = json.loads((target / "freeze.json").read_text())
            m[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
            (target / "freeze.json").write_text(json.dumps(m))
    elif fault == "manifest":
        (target / "freeze.json").write_text("{}")
    elif fault == "extra":
        (target / "extra").write_text("")
    else:
        p.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(target)


def test_all_source_rows_remain_scored_under_the_original_policy():
    result = audit()
    c = result["counts"]
    assert result["arithmetic_checks_passed"] and not result["implementation_failures"]
    assert (
        c["original_denominator"],
        c["original_matched"],
        c["original_not_matched"],
        c["missing_days"],
    ) == (64, 46, 16, 2)
    assert c["mismatched_components"] == dict(general=3, god=10, human=6)
    assert c["mismatches_with_no_whole_match_under_either_mode"] == 13
    assert c["mismatches_with_an_alternative_whole_match"] == 3
    assert (c["god_cells"], c["human_cells"], c["engine_mode_comparisons"]) == (
        240,
        120,
        186,
    )
    rows = {r["id"]: r for r in result["rows"]}
    assert rows["P42"]["literal_positions"][1] == "天乙"
    assert rows["P42"]["comparison_positions"][1] == "贵人"
    assert [r["id"] for r in rows.values() if r["original_matched"] is None] == [
        "P33",
        "P45",
    ]
    assert [
        r["id"]
        for r in rows.values()
        if r["original_matched"] is False and r["modes_matching_whole"]
    ] == ["P34", "P41", "P44"]
    assert rows["P64"]["human_day_stem_constraints"] == ["甲", "己"]
    assert (
        rows["P64"]["source_day"] == "乙卯"
        and rows["P64"]["general_required_by_diagram"] == "午"
    )
    assert all(r["source_day_emended"] is False for r in rows.values())
    assert (
        not result["original_classical_acceptance_passed"]
        and not result["goal_complete"]
    )


def test_mixed_system_geng_start_is_detected_against_independent_reference(monkeypatch):
    import fatebridge.core.metaphysics.jinkou as production

    original = production._build_guishen_mapping
    bad = copy.deepcopy(reference())
    bad["day_starts"]["庚"] = "未"

    def wrong(stem, hour, explicit=None):
        if stem == "庚" and (
            explicit is True or explicit is None and hour in bad["day_branches"]
        ):
            return "未", god_map(bad, stem, True)
        return original(stem, hour, explicit)

    monkeypatch.setattr(production, "_build_guishen_mapping", wrong)
    result = audit()
    assert not result["arithmetic_checks_passed"]
    assert any(
        f["kind"] == "god_grid" and f["stem"] == "庚" and f["day"] is True
        for f in result["implementation_failures"]
    )


def test_predeclared_wrong_directions_are_discriminated_without_changing_source_score():
    result = audit()
    assert result["negative_control_changed_god_cells"] == dict(
        swap_day_and_night=200,
        reverse_directions=200,
        omit_night_reversal=100,
        wrong_sun_start_for_geng=12,
    )
    assert result["original_score_unchanged"]
    assert (
        result["source_emendations"]
        == result["new_independent_classical_cases"]
        == result["new_model_processes"]
        == 0
    )
