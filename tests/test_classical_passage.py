"""Source-position facts remain separate from a proposed force correction."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.classical_passage import build_passage_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_classical_passage import ClassicalPassage, PassagePath


def chart(text):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))


def evidence(text):
    pillars = chart(text)
    assessment = ElementAnalysis.analyze_day_master_strength(pillars)["assessment"]
    return pillars, assessment, build_passage_evidence(pillars, assessment)


def test_source_four_clashes_have_two_positioned_branch_intermediaries():
    pillars = chart("癸酉 甲子 丁卯 丙午")
    assessment = ElementAnalysis.analyze_day_master_strength(pillars)["assessment"]
    before = deepcopy(assessment)
    result = build_passage_evidence(pillars, assessment)
    assert result["summary"]["visible_path_count"] == 2
    assert [p["elements"] for p in result["principal_hidden_paths"]] == [
        ["金", "水", "木"],
        ["水", "木", "火"],
    ]
    assert [p["positions"] for p in result["principal_hidden_paths"]] == [
        ["year", "month", "day"],
        ["month", "day", "hour"],
    ]
    assert result["visible_paths"][0]["to_node"] == "day:stem:丁"
    assert result["visible_paths"][1]["position_status"] == "between_with_gap"
    assert all(
        p["effective_passage"] == "not_adjudicated" for p in result["all_hidden_paths"]
    )
    assert len(result["all_hidden_paths"]) > len(result["principal_hidden_paths"])
    assert {
        n["stem"]
        for n in result["nodes"]
        if n["pillar"] == "hour" and n["plane"] == "hidden"
    } == {"丁", "己"}
    assert result["summary"]["calculation_effect"] == "none"
    assert assessment == before and assessment["strength_level"] == "弱"
    assert (
        build_passage_evidence(dict(reversed(list(pillars.items()))), assessment)
        == result
    )
    ClassicalPassage.model_validate(result)


def test_separated_or_outside_intermediary_is_not_relabelled_as_contiguous():
    _, _, result = evidence("庚寅 甲辰 壬子 丙午")
    path = next(
        p for p in result["visible_paths"] if p["elements"] == ["金", "水", "木"]
    )
    assert path["positions"] == ["year", "day", "month"]
    assert path["position_status"] == "outside_interval"
    with pytest.raises(
        ValidationError, match="已给通关路径节点引用和事实必须容许同一实体生克链"
    ):
        PassagePath.model_validate(
            {**path, "position_status": "adjacent_mediator_between"}
        )
    with pytest.raises(
        ValidationError, match="已给通关路径节点引用和事实必须容许同一实体生克链"
    ):
        PassagePath.model_validate({**path, "via_node": "hour:stem:壬"})
    with pytest.raises(ValidationError):
        PassagePath.model_validate({**path, "effective_passage": "effective"})
    PassagePath.model_validate({"position_status": "outside_interval"})


def test_absent_assessment_is_unknown_and_no_solver_is_called(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Passage evidence must use the supplied calculation")

    monkeypatch.setattr(ElementAnalysis, "analyze_day_master_strength", forbidden)
    result = build_passage_evidence(chart("癸酉 甲子 丁卯 丙午"), {})
    assert all(n["remaining_root_state"] == "not_supplied" for n in result["nodes"])
    assert all(
        p["all_nodes_have_remaining_roots"] is None for p in result["visible_paths"]
    )
    assert all(n["binding_state"] == "not_supplied" for n in result["nodes"])


def test_synthetic_energy_does_not_manufacture_an_intermediary_root():
    pillars, assessment, _ = evidence("癸酉 甲子 丁卯 丙午")
    changed = deepcopy(assessment)
    for row in changed["hidden_stem_ledger"]:
        if row["element"] == "水":
            row.update(
                remaining_mass=0.0, retention_fraction=0.0, engineering_energy=0.0
            )
    changed["combination_contributions"].append({"element": "水", "mass": 100.0})
    result = build_passage_evidence(pillars, changed)
    assert all(not p["all_nodes_have_remaining_roots"] for p in result["visible_paths"])


def test_binding_is_read_from_the_same_assessment_and_subsets_are_independent():
    _, _, result = evidence("戊寅 癸亥 丁未 辛亥")
    stems = {n["pillar"]: n for n in result["nodes"] if n["plane"] == "stem"}
    assert (
        stems["year"]["binding_state"]
        == stems["month"]["binding_state"]
        == "binding_recorded"
    )
    _, _, result = evidence("癸酉 甲子 丁卯 丙午")
    original = deepcopy(result["all_hidden_paths"])
    result["principal_hidden_paths"][0]["positions"][0] = "hour"
    assert result["all_hidden_paths"] == original


@pytest.mark.parametrize(
    "text, seal, body",
    [
        ("壬辰 壬子 丙寅 癸巳", "甲", "丙"),
        ("戊午 己未 壬申 辛亥", "庚", "壬"),
    ],
)
def test_day_branch_seal_can_be_an_observed_cross_plane_intermediary(text, seal, body):
    # 官殺 PDF215–216 explicitly describe these hidden seals feeding the body.
    _, _, result = evidence(text)
    paths = [
        p
        for p in result["mixed_paths"]
        if p["via_node"] == f"day:hidden:{seal}" and p["to_node"] == f"day:stem:{body}"
    ]
    assert paths and all(p["position_status"] == "shared_pillar_step" for p in paths)
    assert all(p["effective_passage"] == "not_adjudicated" for p in paths)
    assert not any(
        p["position_status"] == "adjacent_mediator_between"
        for p in result["visible_paths"]
    )
    ClassicalPassage.model_validate(result)
