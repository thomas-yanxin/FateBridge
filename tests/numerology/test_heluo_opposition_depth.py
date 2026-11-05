"""Printed missing-original premise, separately from target/body presence."""

import copy
import hashlib
import itertools
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import heluo
from fatebridge.core import heluo_opposition as op
from fatebridge.core.heluo_body import body_evidence
from fatebridge.core.output_numerology import (
    HeluoYuanqiOpposition,
    HeluoYuanqiOppositionCondition,
)
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parents[1] / "fixtures/heluo_yuanqi_opposition_v1"
REFERENCE = json.loads((ROOT / "verified-readings.json").read_text())


def evidence(year, up, low, other=None):
    yuan = {"tian": heluo.GAN_YUAN[year[0]], "di": heluo.ZHI_YUAN[year[1]]}
    fan = {"tian": heluo.GAN_FAN[year[0]], "di": heluo.ZHI_FAN[year[1]]}
    phases = {}
    for phase, pair in [("xian", (up, low)), ("hou", other or (up, low))]:
        bits = heluo.gua_lines(*pair)
        phases[phase] = {
            "gua": heluo.lines_to_gua(bits)["name"],
            "trigrams": heluo._san_cai(bits),
        }
    bodies = body_evidence(year, phases, yuan)["bodies"]
    return op.opposition_evidence(year, bodies, yuan, fan), bodies, yuan, fan


@pytest.mark.parametrize("probe", REFERENCE["hand_derived_probes"])
def test_hand_worked_absence_presence_and_direct_only_comparison(probe):
    result, _, _, _ = evidence(probe["year"], probe["up"], probe["low"])
    HeluoYuanqiOpposition.model_validate(result)
    for phase in result["phases"]:
        condition = next(r for r in phase["conditions"] if r["kind"] == probe["kind"])
        p = phase["phase"] + "."
        assert condition["yuan_body_ids"] == [p + k for k in probe["yuan_ids"]]
        assert condition["fan_body_ids"] == [p + k for k in probe["fan_ids"]]
        assert condition["condition_match"] is probe["match"]
        assert condition["direct_only_condition_match"] is probe["direct_match"]
        assert condition["rescue_match"] is None
    assert result["full_rescue_assessment"] is False


def test_other_phase_targets_cannot_supply_missing_current_phase_facts():
    result, _, _, _ = evidence("甲戌", "坤", "坤", other=("乾", "乾"))
    a, b = result["phases"]
    assert all(r["condition_match"] for r in a["conditions"])
    assert not any(r["condition_match"] for r in b["conditions"])
    assert all(r["yuan_body_ids"] == [] for r in a["conditions"])
    assert all(r["fan_body_ids"] == [] for r in b["conditions"])
    assert "no_cross_phase_substitution" in result["body_scope_policy"]


def test_mapping_groups_against_all_sixty_years_and_all_hexagrams():
    # Exhaustive rule-derived probes; not 3840 external horoscope references.
    mapping = {
        s: r for r in REFERENCE["runtime_source"]["mappings"] for s in r["symbols"]
    }
    for i in range(60):
        year = heluo.GAN[i % 10] + heluo.ZHI[i % 12]
        for up, low in itertools.product(heluo.TRIGRAM_BITS, repeat=2):
            result, bodies, _, _ = evidence(year, up, low)
            for phase in result["phases"]:
                for condition in phase["conditions"]:
                    symbol = year[0 if condition["kind"] == "tian" else 1]
                    row = mapping[symbol]
                    assert (condition["yuan_trigram"], condition["fan_trigram"]) == (
                        row["yuan"],
                        row["fan"],
                    )
                    found = {
                        r["trigram"] for r in bodies if r["phase"] == phase["phase"]
                    }
                    assert condition["condition_match"] is (
                        row["yuan"] not in found and row["fan"] in found
                    )


def test_original_pages_and_distinct_full_hexagram_operations():
    for row in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    for row in REFERENCE["page35_full_hexagram_diagram_context"]:
        assert heluo.lines_to_gua(row["before_bits"])["name"] == row["before"]
        assert heluo.lines_to_gua(row["after_bits"])["name"] == row["after"]
        expected = (
            [1 - b for b in row["before_bits"]]
            if row["operation"] == "complement"
            else row["before_bits"][::-1]
        )
        assert expected == row["after_bits"]
    assert (
        REFERENCE["new_original_horoscopes"] == REFERENCE["new_calendar_instants"] == 0
    )
    assert not REFERENCE["independent_second_review_completed"]


@pytest.mark.parametrize(
    "fault",
    ["year", "target", "fan", "nuclear", "duplicate", "phase", "position", "gua"],
)
def test_runtime_context_conflicts_are_internal_source_failures(fault):
    _, bodies, yuan, fan = evidence("甲戌", "坤", "坤")
    year = "甲戌"
    if fault == "year":
        year = "甲丑"
    elif fault == "target":
        yuan["tian"] = "坤"
    elif fault == "fan":
        fan["di"] = "乾"
    elif fault == "nuclear":
        bodies[1]["trigram"] = "乾"
    elif fault == "duplicate":
        bodies[1] = copy.deepcopy(bodies[0])
    elif fault == "phase":
        bodies[4]["phase"] = "xian"
    elif fault == "position":
        bodies[0]["line_positions"][0] = True
    else:
        bodies[0]["gua"] = "乾為天"
    with pytest.raises(NumerologySourceError) as err:
        op.opposition_evidence(year, bodies, yuan, fan)
    assert err.value.reason == "runtime_heluo_yuanqi_context_conflict"


@pytest.mark.parametrize("fault", ["mapping", "literal", "review", "missing"])
def test_nonempty_resource_changes_cannot_keep_the_same_source_version(
    fault, tmp_path, monkeypatch
):
    data = json.loads(op.SOURCE_PATH.read_text())
    path = tmp_path / "source.json"
    if fault == "mapping":
        data["mappings"][0]["fan"] = "乾"
    elif fault == "literal":
        data["absence_literal"] = "有坤就是相反"
    elif fault == "review":
        data["review_status"] = "independent_review_complete"
    if fault != "missing":
        path.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(op, "SOURCE_PATH", path)
    op._source.cache_clear()
    try:
        with pytest.raises(NumerologySourceError) as err:
            evidence("甲戌", "坤", "坤")
        assert err.value.reason == "invalid_heluo_opposition_source"
    finally:
        op._source.cache_clear()


def test_content_identity_is_format_independent_and_caches_actual_loaded_bytes(
    tmp_path, monkeypatch
):
    data = json.loads(op.SOURCE_PATH.read_text())
    path = tmp_path / "source.json"
    path.write_text(json.dumps(data, ensure_ascii=True, sort_keys=True, indent=4))
    monkeypatch.setattr(op, "SOURCE_PATH", path)
    op._source.cache_clear()
    try:
        old, _, _, _ = evidence("甲戌", "坤", "坤")
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        assert (
            old["content_sha256"] == op.CONTENT_SHA256
            and old["collation_sha256"] == expected
        )
        path.write_text("{}")
        cached, _, _, _ = evidence("甲戌", "坤", "坤")
        assert cached["collation_sha256"] == expected
    finally:
        op._source.cache_clear()


@pytest.mark.parametrize(
    "change", [{"condition_match": True}, {"yuan_absent": True}, {"rescue_match": True}]
)
def test_types_do_not_erase_known_premises_or_invent_rescue(change):
    result, _, _, _ = evidence("甲子", "坤", "乾")
    row = copy.deepcopy(result["phases"][0]["conditions"][0])
    row.update(change)
    with pytest.raises(ValidationError):
        HeluoYuanqiOppositionCondition.model_validate(row)
    HeluoYuanqiOppositionCondition.model_validate({"condition_match": True})
    with pytest.raises(ValidationError):
        HeluoYuanqiOpposition.model_validate({"full_rescue_assessment": True})


def test_returned_conditions_do_not_mutate_source_or_other_phase():
    result, _, _, _ = evidence("甲戌", "坤", "坤")
    result["phases"][0]["conditions"][0]["fan_body_ids"].clear()
    assert result["phases"][1]["conditions"][0]["fan_body_ids"]
    again, _, _, _ = evidence("甲戌", "坤", "坤")
    assert again["phases"][0]["conditions"][0]["fan_body_ids"]


def test_draft_withdrawal_is_preserved_and_not_counted_as_a_product_bug():
    initial = (ROOT / "reference.json").read_bytes()
    amendments = (ROOT / "amendments.json").read_bytes()
    assert REFERENCE["initial_reference_sha256"] == hashlib.sha256(initial).hexdigest()
    assert REFERENCE["amendments_sha256"] == hashlib.sha256(amendments).hexdigest()
    assert json.loads(initial)["hand_derived_probes"][5]["year"] == "庚卯"
    assert REFERENCE["hand_derived_probes"][5]["year"] == "庚辰"


@pytest.mark.parametrize("fault", ["drop_absence", "select_rescue"])
def test_audit_detects_an_overstated_source_condition(monkeypatch, fault):
    from scripts.numerology import audit_numerology as audit

    original = op.opposition_evidence

    def wrong(*args, **kwargs):
        result = original(*args, **kwargs)
        if fault == "drop_absence":
            for phase in result["phases"]:
                for row in phase["conditions"]:
                    row["condition_match"] = row["fan_present"]
        else:
            result["full_rescue_assessment"] = True
        return result

    monkeypatch.setattr(op, "opposition_evidence", wrong)
    result = audit.yuanqi_opposition_checks()
    assert not result["checks_passed"] and result["failures"]
