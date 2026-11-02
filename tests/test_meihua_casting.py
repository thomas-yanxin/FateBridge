"""Source casting, original examples and omitted facts remain distinguishable."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_casting import audit_explicit_casts

REFERENCES = Path(__file__).parent / "fixtures/meihua_casting_v1"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def test_all_frozen_original_examples_and_rule_probes():
    report = audit_explicit_casts(REFERENCES)
    assert report["selected_calculation_checks_passed"]
    assert report["original_worked_example_count"] == 9
    assert report["independent_rule_probe_count"] == 4
    assert len(report["semantic_findings"]) == 4
    assert not report["full_classical_conformance_established"]
    assert report["real_world_prospective_sample_count"] == 0


def test_oracle_tampering_is_rejected_and_disagreement_cannot_pass(tmp_path):
    reference = tmp_path / "fixtures/meihua_casting_v1"
    shutil.copytree(REFERENCES, reference)
    shutil.copytree(
        REFERENCES.parent / "meihua_v1/sources", tmp_path / "fixtures/meihua_v1/sources"
    )
    path = reference / "cases.json"
    cases = json.loads(path.read_text())
    cases["cases"][0]["expected"]["moving_line"] = 2
    path.write_text(json.dumps(cases, ensure_ascii=False))
    with pytest.raises(ValueError, match="oracle changed"):
        audit_explicit_casts(reference)
    manifest_path = reference / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["cases_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))
    report = audit_explicit_casts(reference)
    assert not report["selected_calculation_checks_passed"]
    assert report["cases"][0]["disagreements"] == [
        {"field": "moving_line", "expected": 2, "actual": 4}
    ]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_method_source_and_original_inputs_are_preserved(case):
    r = calculate_meihua_cast(casting=case["input"])
    cast = r["meihua"]
    assert cast["seed"]["moving_line"] == case["expected"]["moving_line"]
    assert cast["ruleset"]["id"] == "meihua_explicit_casts_v1"
    assert cast["rule_trace"][0]["rule_id"] == case["input"]["method"]
    assert "time_seed" not in {row["rule_id"] for row in cast["rule_trace"]}
    assert "year_branch" not in cast["seed"]
    assert cast["seasonal_strength"] is None
    assert cast["evidence_scope"]["missing_context"] == ["season_month_branch"]
    assert cast["calendar_policy"]["date_basis"] == "no_civil_datetime_supplied"
    for key, value in case["input"].items():
        assert r["input_normalized"]["casting"][key] == value


@pytest.mark.parametrize("hour", ["子", "巳", "酉", "亥"])
def test_existing_cast_does_not_use_clock_or_recast(hour):
    # The input has no clock parameter; an unrelated question must not alter it.
    supplied = {"method": "existing", "hexagram_code": "111111", "moving_line": 6}
    r = calculate_meihua_cast(casting=supplied, question=f"虚构{hour}时的原卦复盘")
    assert r["meihua"]["base_hexagram"]["binary_code"] == "111111"
    assert r["meihua"]["changed_hexagram"]["binary_code"] == "111110"
    assert r["meihua"]["seed"]["moving_line"] == 6
    assert r["meihua"]["calendar_policy"]["hour_basis"] == "not_used_for_cast"


def test_zhang_chi_excludes_cun_and_chi_cun_excludes_fen():
    a = calculate_meihua_cast(
        casting={"method": "length_zhang_chi", "zhang": 12, "chi": 3, "cun": 1}
    )
    b = calculate_meihua_cast(
        casting={"method": "length_zhang_chi", "zhang": 12, "chi": 3, "cun": 9}
    )
    assert a["meihua"]["seed"]["moving_line"] == b["meihua"]["seed"]["moving_line"] == 3
    assert a["meihua"]["seed"]["ignored_components"] == {"cun": 1}
    c = calculate_meihua_cast(
        casting={
            "method": "length_chi_cun",
            "chi": 12,
            "cun": 3,
            "fen": 9,
            "hour_branch": "酉",
        }
    )
    assert c["meihua"]["seed"]["moving_line"] == 1
    assert c["meihua"]["seed"]["ignored_components"] == {"fen": 9}


def test_sound_counts_above_eight_do_not_hide_the_unchosen_convention():
    raw = {
        "method": "sound_groups",
        "first_count": 12,
        "second_count": 5,
        "hour_branch": "酉",
    }
    a = calculate_meihua_cast(casting=raw)
    b = calculate_meihua_cast(casting={**raw, "line_sum_basis": "trigram_numbers"})
    assert (
        a["meihua"]["seed"]["moving_line"],
        a["meihua"]["seed"]["alternate_moving_line"],
    ) == (3, 1)
    assert (
        b["meihua"]["seed"]["moving_line"],
        b["meihua"]["seed"]["alternate_moving_line"],
    ) == (1, 3)
    assert "counting_convention" in a["interpretation"]["evidence_scope"]
    assert a["meihua"]["base_hexagram"] == b["meihua"]["base_hexagram"]
    assert a["meihua"]["changed_hexagram"] != b["meihua"]["changed_hexagram"]


def test_odd_character_partition_and_glyph_counts_are_not_dictionary_guesses():
    r = calculate_meihua_cast(
        casting={"method": "text_strokes", "strokes": [6, 8, 3], "text": "示例字"}
    )
    assert r["meihua"]["seed"]["raw_upper_number"] == 6
    assert r["meihua"]["seed"]["raw_lower_number"] == 11
    assert r["meihua"]["seed"]["moving_line"] == 5
    # 西 is commonly six strokes today; the cited unusual glyph was recorded
    # as seven. The engine must preserve the supplied original glyph count.
    r = calculate_meihua_cast(casting=CASES[2]["input"])
    assert r["meihua"]["seed"]["raw_upper_number"] == 7


def test_counting_ambiguity_can_reverse_body_use_and_must_remain_visible():
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
        }
    )
    variants = result["meihua"]["counting_variants"]
    assert [
        (v["moving_line"], v["body"], v["body_use_relation"]) for v in variants
    ] == [(1, "离", "体克用"), (5, "乾", "用克体")]
    assert result["interpretation"]["status"] == "conditional_on_declared_convention"
    assert result["summary"].startswith("原声数与卦序数取爻有分歧")


def test_season_context_changes_only_seasonal_interpretation():
    source = CASES[5]["input"]
    a = calculate_meihua_cast(casting=source)
    b = calculate_meihua_cast(casting=source, season_month_branch="子")
    assert a["meihua"]["seed"] == b["meihua"]["seed"]
    assert a["meihua"]["base_hexagram"] == b["meihua"]["base_hexagram"]
    assert b["meihua"]["seasonal_strength"]["trigrams"][0]["strength"] == "衰"
    assert a["meihua"]["seasonal_strength"] is None


def test_explicit_facts_work_without_lunar_or_ephemeris_backends(monkeypatch):
    import fatebridge.core.almanac as almanac
    import fatebridge.core.ephemeris_runtime as runtime

    monkeypatch.setattr(almanac, "LunarDate", None)
    monkeypatch.setattr(runtime, "swe", None)
    result = calculate_meihua_cast(casting=CASES[0]["input"])
    assert "error" not in result
    assert result["meihua"]["base_hexagram"]["binary_code"] == "011111"


@pytest.mark.parametrize(
    "casting",
    [
        {"method": "observed_trigrams", "upper_trigram": "乾", "lower_trigram": "巽"},
        {"method": "length_zhang_chi", "zhang": 0, "chi": 0, "cun": 5},
        {"method": "length_chi_cun", "chi": 12, "cun": 3},
        {"method": "length_zhang_chi", "zhang": True, "chi": 3},
        {"method": "length_zhang_chi", "zhang": 1, "chi": 10},
        {"method": "text_tones", "tones": [1, 2, 3]},
        {"method": "text_tones", "tones": [1, 2, 3, 5]},
        {"method": "text_tones", "tones": [1, 2, 3, 4], "text": "四声"},
        {"method": "text_strokes", "strokes": [6]},
        {
            "method": "single_character_strokes",
            "script_style": "cursive",
            "left_strokes": 3,
            "right_strokes": 7,
            "total_strokes": 10,
        },
        {
            "method": "single_character_strokes",
            "script_style": "regular",
            "left_strokes": 3,
            "right_strokes": 7,
            "total_strokes": 9,
        },
        {"method": "text_count", "character_count": 10},
        {"method": "text_count", "character_count": 101},
        {"method": "existing", "hexagram_code": "111111", "moving_line": 0},
        {"method": "existing", "hexagram_code": "11111x", "moving_line": 1},
        {
            "method": "existing",
            "hexagram_code": "111111",
            "moving_line": 1,
            "hour_branch": "子",
        },
    ],
)
def test_absent_ambiguous_or_mixed_method_inputs_are_rejected(casting):
    with pytest.raises(ValidationError):
        MeihuaCastRequest(casting=casting)
