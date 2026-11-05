"""Source-root categories are neither guessed hidden stems nor strength labels."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.classical import build_classical_overview, classical_snapshot_lines
from fatebridge.core.classical_roots import (
    build_classical_root_profile,
    classify_classical_root,
)
from fatebridge.core.output_classical_roots import ClassicalRootProfile

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "data/bazi_roots_v1/reference.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize(
    "case", REFERENCE["cases"], ids=lambda c: c["stem"] + c["branch"]
)
def test_root_categories_match_manually_read_source_examples(case):
    actual = classify_classical_root(case["stem"], case["branch"])
    assert actual["kind"] == case["kind"]
    assert actual["hidden_element_present"] == case["hidden_element_present"]


def test_storage_and_residual_are_not_the_rank_in_the_hidden_stem_list():
    assert classify_classical_root("甲", "未")["kind"] == "storage_root"
    assert classify_classical_root("乙", "辰")["kind"] == "residual_root"
    assert classify_classical_root("庚", "巳")["source_weight_class"] == "heavy"


@pytest.mark.parametrize("stem,branch", [("乙", "寅"), ("癸", "亥")])
def test_yin_prosperity_root_is_distinct_from_yang_blade_qualification(stem, branch):
    root = classify_classical_root(stem, branch)
    assert root["kind"] == "prosperity_root"
    assert root["source_weight_class"] == "heavy"
    assert root["hidden_element_present"] is True


def test_profile_preserves_positions_and_does_not_adjudicate_clash_root_loss():
    chart = dict(
        zip(
            ("year", "month", "day", "hour"),
            map(tuple, ["甲亥", "乙巳", "甲寅", "丁亥"]),
        )
    )
    result = build_classical_root_profile(chart)
    assert result["roots"][0]["clash_partners"] == ["month"]
    assert result["roots"][3]["clash_partners"] == ["month"]
    assert result["global_strength_status"] == "not_adjudicated"
    assert all(
        r["effect_status"] == "root_effect_not_adjudicated" for r in result["roots"]
    )
    assert result == build_classical_root_profile(dict(reversed(list(chart.items()))))
    assert result["source"]["source_sha256"] == REFERENCE["source_sha256"]


def test_yin_growth_remains_a_textual_reference_without_inventing_hidden_fire():
    chart = {name: ("丁", "酉") for name in ("year", "month", "day", "hour")}
    overview = build_classical_overview(chart)
    profile = overview["root_profile"]
    assert profile["heavy_root_positions"] == []
    assert profile["yin_growth_reference_positions"] == ["year", "month", "day", "hour"]
    assert all(r["matching_hidden_stems"] == [] for r in profile["roots"])
    text = "\n".join(classical_snapshot_lines(overview))
    assert "阴长生原典参考" in text and "未判根损" in text
    assert "身强" not in text


def test_published_root_fields_validate_types_before_projection():
    with pytest.raises(ValidationError):
        ClassicalRootProfile.model_validate(
            {"roots": [{"hidden_element_present": "yes"}]}
        )
    with pytest.raises(ValidationError, match="补造"):
        ClassicalRootProfile.model_validate(
            {
                "roots": [
                    {
                        "kind": "yin_growth_reference",
                        "hidden_element_present": True,
                        "matching_hidden_stems": ["丁"],
                    }
                ]
            }
        )
