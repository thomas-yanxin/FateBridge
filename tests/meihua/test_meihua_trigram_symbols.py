"""Literal source and geometry controls, never observed prediction scores."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.meihua_trigram_symbols import (
    _layer,
    apply_trigram_relation_symbols,
    trigram_symbols_ruleset,
)
from fatebridge.services.meihua import calculate_meihua_cast

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/meihua_trigram_symbols_v1"
GEOMETRY = json.loads((FIXTURE / "geometry384.json").read_text())


def calculate(code="010111", line=4, **kwargs):
    return calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": code, "moving_line": line},
        **kwargs,
    )


def resolve(result, path):
    for key in path.split("."):
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def test_source_profile_is_exactly_the_preimplementation_visual_reference():
    expected = json.loads((FIXTURE / "profile.json").read_text())
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_text())
    assert not freeze["new_module_present"]
    for name in ["profile.json", "geometry384.json"]:
        assert (
            hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
            == freeze["files"][name]
        )
    for index in [60, 61, 62]:
        assert (
            hashlib.sha256((FIXTURE / f"nlc-index{index}.png").read_bytes()).hexdigest()
            == freeze["files"][f"nlc-index{index}-large.png"]
        )
    assert trigram_symbols_ruleset() == expected
    assert len(expected["rules"]) == 16
    assert (
        expected["source"]["raw_sha256"]
        == "af608094ab11ae209eae91a9365565e7c9cff604aac3da5e753e04d1cc4598c0"
    )
    altered = trigram_symbols_ruleset()
    altered["rules"][0]["quote"] = "changed"
    assert trigram_symbols_ruleset() == expected


def test_packaged_reference_bundle_retains_every_original_frozen_file():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["source_and_geometry_frozen_before_production"]
    assert manifest["fixture_packaged_after_implementation"]
    for name, expected in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert (
            hashlib.sha256((FIXTURE / "references" / name).read_bytes()).hexdigest()
            == expected
        )


@pytest.mark.parametrize(
    "case", GEOMETRY, ids=lambda c: c["code"] + ":" + str(c["line"])
)
def test_all_384_frozen_geometries_select_actual_role_and_literal_source(case):
    result = calculate(case["code"], case["line"])
    layer = result["interpretation"]["trigram_relation_symbols"]["selected"]
    assert layer["body"] == case["body"]
    assert result["meihua"]["mutual_hexagram"]["binary_code"] == case["mutual_code"]
    rules = {
        r["id"]: r for r in json.loads((FIXTURE / "profile.json").read_text())["rules"]
    }
    for actual, expected in zip(layer["role_evaluations"], case["rows"], strict=True):
        assert {k: actual[k] for k in ["role", "trigram", "relation"]} == {
            k: expected[k] for k in ["role", "trigram", "relation"]
        }
        assert actual["clause_id"] == expected["expected_clause_id"]
        assert actual["quote"] == (
            rules[actual["clause_id"]]["quote"] if actual["clause_id"] else None
        )
        assert resolve(result, actual["body_fact_path"]) == layer["body"]
        assert resolve(result, actual["trigram_fact_path"]) == actual["trigram"]
        assert resolve(result, actual["relation_fact_path"]) == actual["relation"]
        assert (
            resolve(result, actual["control_fact_path"])
            == actual["internal_control_qualification"]
        )
        assert resolve(result, actual["strength_fact_path"]) == actual["strength"]
        assert actual["effective_net_imagery"] is None
        assert not actual["real_person_or_event_inferred"]


def test_all_sixteen_rules_reached_and_same_element_never_substitutes_trigram():
    ids = {r["expected_clause_id"] for c in GEOMETRY for r in c["rows"]} - {None}
    assert ids == {r["id"] for r in trigram_symbols_ruleset()["rules"]}
    qian = calculate("010111", 4)["interpretation"]["trigram_relation_symbols"][
        "selected"
    ]["role_evaluations"][0]
    dui = calculate("010110", 4)["interpretation"]["trigram_relation_symbols"][
        "selected"
    ]["role_evaluations"][0]
    assert qian["relation"] == dui["relation"] == "用生体"
    assert qian["clause_id"] == "qian_generates_body"
    assert dui["clause_id"] == "dui_generates_body"
    assert "公門" in qian["quote"] and "朋友講習" in dui["quote"]
    assert qian["quote"] != dui["quote"]


def test_printed_south_and_other_variants_are_not_corrected_from_common_tables():
    profile = trigram_symbols_ruleset()
    rules = {r["id"]: r for r in profile["rules"]}
    assert "謀事乃南方之人" in rules["xun_controls_body"]["quote"]
    assert "東南" not in rules["xun_controls_body"]["quote"]
    assert "東南" in rules["xun_generates_body"]["quote"]
    assert "進入" in rules["kan_generates_body"]["quote"]
    assert "市口" in rules["dui_generates_body"]["quote"]
    assert all(
        not r["used_to_override_selected_edition"] for r in profile["selected_variants"]
    )


@pytest.mark.parametrize("branch", [None, *"子丑寅卯辰巳午未申酉戌亥"])
def test_strength_unknown_and_direct_control_remain_qualifications_not_raw_rule_erasure(
    branch,
):
    for code, line in [("010111", 4), ("100010", 2), ("110011", 3)]:
        p = calculate(code, line, season_month_branch=branch)
        layer = p["interpretation"]["trigram_relation_symbols"]["selected"]
        for row in layer["role_evaluations"]:
            assert (
                row["clause_id"] is not None
                if row["relation"] in ["用生体", "用克体"]
                else row["clause_id"] is None
            )
            assert (
                row["strength"] is None
                if branch is None
                else row["strength"] in ["旺", "衰", "原文未定"]
            )
            assert row["effective_net_imagery"] is None
        assert (
            layer["net_verdict"]
            is layer["event_time"]
            is layer["success_probability"]
            is None
        )


@pytest.mark.parametrize(
    "topic",
    ["general", "planning", "reputation", "wealth", "transaction", "travel", "meeting"],
)
def test_every_count_candidate_owns_its_body_and_fact_paths(topic):
    p = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
        },
        interpretation_topic=topic,
        season_month_branch="申",
    )
    root = p["interpretation"]["trigram_relation_symbols"]
    assert len(root["counting_candidates"]) == 2
    assert len({r["reading"]["body"] for r in root["counting_candidates"]}) == 2
    for i, row in enumerate(root["counting_candidates"]):
        assert (
            row["reading"]["body"] == p["interpretation"]["casting_readings"][i]["body"]
        )
        for v in row["reading"]["role_evaluations"]:
            assert v["body_fact_path"].startswith(f"meihua.counting_variants.{i}.")
            assert resolve(p, v["trigram_fact_path"]) == v["trigram"]
            assert (
                resolve(p, v["control_fact_path"])
                == v["internal_control_qualification"]
            )
            assert resolve(p, v["strength_fact_path"]) == v["strength"]


def test_no_match_does_not_activate_ambiguous_closing_clause_or_infer_absence():
    p = next(
        c for c in GEOMETRY if all(r["expected_clause_id"] is None for r in c["rows"])
    )
    layer = calculate(p["code"], p["line"])["interpretation"][
        "trigram_relation_symbols"
    ]["selected"]
    assert not layer["matched_clause_ids"]
    assert not layer["closing_clause_automatically_applied"]
    assert "不反推" in layer["summary"]


def test_weather_uses_no_human_body_use_symbols():
    p = calculate(interpretation_topic="weather", weather_context={"season": "winter"})
    assert p["interpretation"]["trigram_relation_symbols"] is None


@pytest.mark.parametrize("part", ["control", "strength", "stage_order"])
def test_cross_cast_qualifications_are_rejected(part):
    p = calculate()
    cast = p["meihua"]
    interpretation = p["interpretation"]
    stages = copy.deepcopy(cast["stage_relations"])
    control = copy.deepcopy(interpretation["internal_countercontrol"])
    strength = copy.deepcopy(interpretation["seasonal_qualification"])
    if part == "control":
        control["nodes"][1]["trigram"] = "兑"
    elif part == "strength":
        strength["roles"][0]["fact_path"] = "another_cast"
    else:
        stages.reverse()
    with pytest.raises(ValueError):
        _layer(
            stages,
            control,
            strength,
            fact_prefix="meihua",
            interpretation_prefix="interpretation",
        )


def test_annotator_does_not_mutate_existing_facts_or_summary():
    result = calculate()
    cast = copy.deepcopy(result["meihua"])
    before = copy.deepcopy(result["interpretation"])
    before.pop("trigram_relation_symbols")
    actual = copy.deepcopy(before)
    apply_trigram_relation_symbols(cast, actual)
    actual.pop("trigram_relation_symbols")
    assert actual == before and cast == result["meihua"]
