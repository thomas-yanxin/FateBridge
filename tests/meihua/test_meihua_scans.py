"""Missing classical object-count method, raw hours and visible ambiguity."""

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_scans import audit_scanned_rules, reference_bundle

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_scan_v1"
CASES = json.loads((REFERENCES / "object-count-cases.json").read_text())["cases"]


def test_selected_scans_and_manual_probes_do_not_become_full_book_acceptance():
    report = audit_scanned_rules(REFERENCES)
    assert report["selected_calculation_checks_passed"]
    assert len(report["manual_facsimile_readings"]) == 7
    assert report["independent_rule_probe_count"] == 5
    assert report["new_historical_worked_examples"] == 0
    assert not report["full_text_conformance_established"]
    assert report["real_world_observations"] == 0


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_actual_count_and_hour_are_preserved_without_calendar_or_scene_inference(case):
    result = calculate_meihua_cast(casting=case["input"])
    cast = result["meihua"]
    assert cast["seed"]["raw_upper_number"] == case["input"]["count"]
    assert cast["seed"]["moving_line"] == case["expected"]["moving_line"]
    assert cast["base_hexagram"]["binary_code"] == case["expected"]["base_code"]
    assert cast["rule_trace"][0]["rule_id"] == "object_count"
    assert cast["seasonal_strength"] is None
    assert "object_count" not in cast["evidence_scope"]["not_implemented"]
    assert "year_branch" not in cast["seed"]


@pytest.mark.parametrize(
    "branch,hour,line", [("酉", 10, 5), ("戌", 11, 6), ("亥", 12, 1)]
)
@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_line_uses_original_late_hour_once_even_when_lower_trigram_is_reduced(
    branch, hour, line, basis
):
    cast = calculate_meihua_cast(
        casting={
            "method": "object_count",
            "count": 1,
            "hour_branch": branch,
            "line_sum_basis": basis,
        }
    )["meihua"]
    assert cast["seed"]["lower_number"] == hour - 8
    assert cast["seed"]["line_sum"] == 1 + hour
    assert cast["seed"]["moving_line"] == line
    assert not cast["counting_variants"]


def test_ambiguous_quantity_can_reverse_original_body_and_changed_relation():
    raw = calculate_meihua_cast(casting=CASES[2]["input"])
    reduced = calculate_meihua_cast(casting=CASES[3]["input"])
    assert raw["meihua"]["seed"]["moving_line"] == 1
    assert reduced["meihua"]["seed"]["moving_line"] == 5
    assert [
        (v["body"], v["moving_line"]) for v in raw["meihua"]["counting_variants"]
    ] == [("乾", 1), ("兑", 5)]
    assert (
        raw["interpretation"]["status"]
        == reduced["interpretation"]["status"]
        == "conditional_on_declared_convention"
    )
    assert raw["summary"].startswith("原物数与上卦卦序数取爻有分歧")
    assert "原声数" not in raw["summary"]
    for variant, case in zip(raw["meihua"]["counting_variants"], CASES[2:4]):
        for key in ("base_hexagram", "changed_hexagram", "mutual_hexagram"):
            assert variant[key]["meaning_source_kind"] == "modern_editorial_summary"
        rows = {r["role"]: r for r in variant["stage_relations"]}
        for role in ("body_mutual", "use_mutual", "changed_use"):
            assert rows[role]["relation"] == case["expected"][role + "_relation"]
        for row in rows.values():
            value = raw
            for part in row["fact_path"].split("."):
                value = value[int(part)] if isinstance(value, list) else value[part]
            assert value["name"] == row["trigram"]
            assert value["element"] == row["element"]


def test_pure_hexagram_alternatives_keep_their_own_changed_mutual():
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 17,
            "second_count": 1,
            "hour_branch": "子",
        }
    )
    # Pure Qian: line 1 changes the bottom only, so its changed mutual stays
    # Qian. Line 3 changes the source of both mutual trigrams to Li/Xun.
    variants = result["meihua"]["counting_variants"]
    assert [v["moving_line"] for v in variants] == [1, 3]
    assert [v["mutual_code"] for v in variants] == ["111111", "101011"]
    assert [(r["role"], r["relation"]) for r in variants[1]["stage_relations"]] == [
        ("use", "体用比和"),
        ("body_mutual", "体克用"),
        ("use_mutual", "用克体"),
        ("changed_use", "体用比和"),
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"count": 0},
        {"count": True},
        {"count": 1.5},
        {"count": "9"},
        {"count": 1000001},
        {"hour_branch": None},
        {"first_count": 9},
    ],
)
def test_invalid_or_cross_method_observations_are_rejected(change):
    casting = {"method": "object_count", "count": 9, "hour_branch": "酉", **change}
    with pytest.raises(ValidationError):
        MeihuaCastRequest(casting=casting)


def test_missing_hour_and_unadjudicated_single_sound_cannot_silently_use_object_count():
    for casting in [
        {"method": "object_count", "count": 9},
        {"method": "sound_count", "count": 9, "hour_branch": "酉"},
    ]:
        with pytest.raises(ValidationError):
            MeihuaCastRequest(casting=casting)


def test_changed_scan_or_manual_expected_answer_invalidates_the_frozen_bundle(tmp_path):
    target = tmp_path / "refs"
    shutil.copytree(REFERENCES, target)
    p = target / "object-count-cases.json"
    p.write_text(p.read_text() + " ")
    with pytest.raises(ValueError, match="Frozen scan reference changed"):
        reference_bundle(target)
