"""Source categories, explicit seasons and actual paths must stay distinct."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.meihua_weather_attributions import (
    build_weather_attributions,
    weather_attribution_profile,
)
from fatebridge.services.meihua import calculate_meihua_cast

REFERENCE = Path(__file__).parent / "fixtures/meihua_weather_attributions_v1"
TRIGRAMS = {
    "111": "乾",
    "110": "兑",
    "101": "离",
    "100": "震",
    "011": "巽",
    "010": "坎",
    "001": "艮",
    "000": "坤",
}


def slots_for(row):
    return [
        {"path": f"meihua.{key}.{pos}", "trigram": TRIGRAMS[bits]}
        for key, code in [
            ("base_hexagram", row["code"]),
            ("mutual_hexagram", row["mutual"]),
            ("changed_hexagram", row["changed"]),
        ]
        for pos, bits in [("upper", code[3:]), ("lower", code[:3])]
    ]


def test_frozen_source_and1920independent_contexts():
    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    assert not manifest["new_component_implementation_exists"]
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest
    geometry = json.loads((REFERENCE / "independent-geometry384.json").read_text())
    by_id = {(r["code"], r["line"]): r for r in geometry["cases"]}
    expected = json.loads((REFERENCE / "expected1920.json").read_text())["cases"]
    assert len(expected) == 1920
    for row in expected:
        result = build_weather_attributions(
            slots_for(by_id[(row["code"], row["moving_line"])]), row["season"]
        )
        actual = [
            {
                "term": term["term"],
                "fact_paths": term["fact_paths"],
                "seasonal_status": term["seasonal_check"]["status"],
            }
            for term in result["terms"]
        ]
        assert actual == row["expected_terms"]
        assert result["single_forecast"] is result["success_probability"] is None
        assert result["mapped_into_frozen_research_labels"] is False


def test_source_order_is_preserved_without_applying_winter_to_hail_or_xian():
    profile = weather_attribution_profile()
    assert profile["clauses"]["metal_attributions"]["quote"] == "乾兌為霜雪霰雹"
    assert (
        profile["clauses"]["metal_attributions"]["comparison_fixed_revision1441921"]
        == "乾、兌為霜雪雹霰"
    )
    by_term = {r["term"]: r for r in profile["terms"]}
    assert (
        by_term["霜"]["seasonal_clause"]
        == by_term["雪"]["seasonal_clause"]
        == "winter_check"
    )
    for term in ["霰", "雹", "日", "虹", "霓"]:
        assert by_term[term]["seasonal_clause"] is None


def test_unknown_season_never_becomes_a_matching_or_nonmatching_season():
    rows = [{"path": str(i), "trigram": t} for i, t in enumerate("乾兑离震艮坎")]
    result = build_weather_attributions(rows, None)
    terms = {r["term"]: r for r in result["terms"]}
    for term in ["霜", "雪", "電", "雷"]:
        assert terms[term]["seasonal_check"]["status"] == "pending_context"
    for term in ["霰", "雹", "日", "虹", "霓"]:
        assert terms[term]["seasonal_check"]["status"] == "no_explicit_season_clause"


def test_offseason_is_not_a_prediction_of_absence_or_an_uncontrolled_verdict():
    rows = [{"path": str(i), "trigram": t} for i, t in enumerate("乾兑离震艮坎")]
    result = build_weather_attributions(rows, "spring")
    for row in result["terms"]:
        check = row["seasonal_check"]
        assert not check["unmatched_season_predicts_absence"]
        assert not check["matched_season_is_effective_weather_verdict"]
        if check["required_season"]:
            assert check["status"] == "season_not_matched"
    assert not result["direct_controls_or_full_chapter_priority_adjudicated"]


def test_no_named_trigram_does_not_supply_an_attribution():
    rows = [{"path": str(i), "trigram": t} for i, t in enumerate("坤艮坎巽艮坤")]
    for row in build_weather_attributions(rows, "winter")["terms"]:
        assert not row["symbol_present"] and not row["fact_paths"]
        assert row["seasonal_check"]["status"] == "not_applicable"


@pytest.mark.parametrize("season", ["", "autumn ", "rain", False])
def test_unknown_or_invalid_season_is_not_invented(season):
    with pytest.raises(ValueError, match="explicit or unknown"):
        build_weather_attributions(
            [{"path": str(i), "trigram": "乾"} for i in range(6)], season
        )


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown"])
def test_incomplete_positions_do_not_turn_into_absence(fault):
    rows = [{"path": str(i), "trigram": "乾"} for i in range(6)]
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows[-1]["path"] = rows[0]["path"]
    else:
        rows[-1]["trigram"] = "?"
    with pytest.raises(ValueError, match="six actual unique"):
        build_weather_attributions(rows, None)


def test_profile_is_deeply_isolated():
    profile = weather_attribution_profile()
    profile["terms"][0]["trigrams"].clear()
    profile["clauses"]["metal_attributions"]["quote"] = "changed"
    fresh = weather_attribution_profile()
    assert fresh["terms"][0]["trigrams"] == ["乾", "兑"]
    assert fresh["clauses"]["metal_attributions"]["quote"] == "乾兌為霜雪霰雹"


def test_each_counting_candidate_points_to_its_own_actual_trigrams():
    out = calculate_meihua_cast(
        casting={"method": "object_count", "count": 9, "hour_branch": "酉"},
        interpretation_topic="weather",
        weather_context={"season": "winter"},
    )
    variants = out["interpretation"]["weather"]["casting_variants"]
    assert len(variants) == 2
    for index, variant in enumerate(variants):
        supplement = variant["symbolic_attributions"]
        assert supplement["profile"]["id"] == "meihua_weather_attributions_nlc1925_v1"
        for row in supplement["terms"]:
            for path in row["fact_paths"]:
                assert path.startswith(f"meihua.counting_variants.{index}.")
                value = out
                for key in path.split("."):
                    value = value[int(key)] if isinstance(value, list) else value[key]
                assert value["name"] in row["trigrams"]
