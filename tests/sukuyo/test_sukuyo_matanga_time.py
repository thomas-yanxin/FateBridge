"""Direct Chinese time chains keep their own units, witnesses and unknowns."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
R1 = ROOT / "tests/data/sukuyo-matanga-before-production-v79.json"
R2 = ROOT / "tests/data/sukuyo-matanga-edition-before-production-v79.json"


def test_entire_source_and_edition_layers_equal_both_before_code_references():
    from fatebridge.core.sukuyo_matanga_time import matanga_time_reference

    result = matanga_time_reference()
    assert result["source_data"] == json.loads(R1.read_bytes())["source_data"]
    assert result["edition_identity"] == json.loads(R2.read_bytes())["edition_identity"]
    assert result["hash_scope"] == "source_data_and_edition_identity_v79"


def test_four_chains_match_independent_literal_factor_products():
    from fatebridge.core.sukuyo_matanga_time import matanga_time_reference

    result = matanga_time_reference()
    assert (
        result["conditional_products"]
        == json.loads(R1.read_bytes())["expected_products"]
    )
    assert result["same_named_units_equated"] is False
    assert result["modern_seconds_per_unit"] is None


def test_year_total_stays_literal_without_normalizing_ancient_yi_or_emending():
    from fatebridge.core.sukuyo_matanga_time import matanga_time_reference

    result = matanga_time_reference()
    assert result["source_data"]["year_total_literal"]["literal"] == (
        "合集一年宿夜明眴，一億百六十萬五十。"
    )
    assert result["conditional_products"]["T1301_blink_chain"]["per_年"] == 97200000
    assert result["annual_total_literal_adjudicated"] is False
    assert "modern_numeric_reading_of_annual_literal" not in result


def test_repeated_cycle_comparison_is_explicitly_conditional():
    from fatebridge.core.sukuyo_matanga_time import matanga_time_reference

    comparison = matanga_time_reference()["strict_repeated_cycle_hypothesis_only"]
    assert comparison["common_years"] == 95
    assert comparison["nineteen_year_seven_intercalations"] == 35
    assert comparison["five_year_two_intercalations"] == 38
    assert comparison["difference"] == 3
    assert comparison["source_periodicity_or_schedule_established"] is False
    assert comparison["rates"] == ["7/19", "2/5"]


def test_witness_namespaces_and_reused_editorial_layers_stay_distinct():
    from fatebridge.core.sukuyo_matanga_time import matanga_time_reference

    result = matanga_time_reference()
    editions = {r["source_id"]: r for r in result["edition_identity"]["sources"]}
    assert editions["T1300"]["source_specific_witness_map"]["wit1"] == "【明】"
    assert editions["T1301"]["source_specific_witness_map"]["wit1"] == "【宋】"
    assert [
        len(s["selected_direct_back_records"]) for s in result["source_data"]["sources"]
    ] == [24, 19]
    links = editions["T1301"]["reused_note_links"]
    assert len(links) == 1
    assert links[0]["reported_corresp"] == "#0416017"
    assert links[0]["matching_actual_n_or_xml_id_records"]
    assert links[0]["multiple_editorial_layers_are_not_independent_witnesses"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        "factor",
        "same_units",
        "seconds",
        "half",
        "precedence",
        "annual_emendation",
        "missing_record",
        "witness_map",
        "missing_reused_note",
        "leap_literal",
    ],
)
def test_changed_source_or_unearned_acceptance_requires_new_review(mutation):
    from fatebridge.core.sukuyo_matanga_time import validate_matanga_data

    data = {
        "source_data": copy.deepcopy(json.loads(R1.read_bytes())["source_data"]),
        "edition_identity": copy.deepcopy(
            json.loads(R2.read_bytes())["edition_identity"]
        ),
    }
    if mutation == "factor":
        data["source_data"]["unit_systems"][0]["steps"][0]["count"] = 30
    elif mutation == "missing_record":
        data["source_data"]["sources"][0]["selected_direct_back_records"].pop()
    elif mutation == "witness_map":
        data["edition_identity"]["sources"][1]["source_specific_witness_map"][
            "wit1"
        ] = "【明】"
    elif mutation == "missing_reused_note":
        data["edition_identity"]["sources"][1]["reused_note_links"].clear()
    elif mutation == "annual_emendation":
        data["source_data"]["year_total_literal"]["literal"] = "97200000"
    elif mutation == "leap_literal":
        data["source_data"]["leap_formulations"]["literal"] = "五年再閏"
    else:
        field = {
            "same_units": "same_named_units_equated",
            "seconds": "modern_seconds_per_unit",
            "half": "hinoo_half_mapping_established",
            "precedence": "leap_short_month_priority_established",
        }[mutation]
        data["source_data"]["scope"][field] = 48 if mutation == "seconds" else True
    with pytest.raises(ValueError):
        validate_matanga_data(data)


def test_upstream_delivers_new_layer_without_relabeling_old_v76_hash():
    from fatebridge.core.sukuyo_upstream_dawn import upstream_reference

    result = upstream_reference()
    assert (
        result["source_bundle_sha256"]
        == "744af87237075bf003bbceed2def968afee781039ab6f706208b565831ff9c83"
    )
    assert result["source_bundle_hash_scope"] == "source_data_only_v76"
    assert (
        result["matanga_time_comparison"]["source_bundle_sha256"]
        != result["source_bundle_sha256"]
    )


def test_native_explanation_preserves_activity_units_literal_and_hypothesis():
    from fatebridge.core.sukuyo_upstream_dawn import upstream_lines, upstream_reference

    text = "\n".join(upstream_lines(upstream_reference()))
    for phrase in [
        "紡綖",
        "三尺",
        "瞬頃",
        "眴",
        "9600",
        "97200000",
        "一億百六十萬五十",
        "十九年",
        "95",
        "35",
        "38",
        "严格重复",
        "未换算现代秒",
        "桧尾",
    ]:
        assert phrase in text


def test_all_prior_dawn_and_apparatus_bundles_remain_unchanged():
    expected = {
        "sukuyo_daybreak_sources.json": "2c78e5f4164b59a8b4343c9398afe1d1bb1d6abab7aef284c1f3ff93ee0f8dea",
        "sukuyo_upstream_dawn_sources.json": "744af87237075bf003bbceed2def968afee781039ab6f706208b565831ff9c83",
        "sukuyo_apparatus_scope.json": "36fa479a3fb57fa90e51644f5ef582dcb218f334cd960b0d0be77ef1920927ec",
    }
    for name, digest in expected.items():
        assert (
            hashlib.sha256(
                (ROOT / "src/fatebridge/data" / name).read_bytes()
            ).hexdigest()
            == digest
        )
