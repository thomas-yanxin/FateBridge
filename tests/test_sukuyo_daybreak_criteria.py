"""Named dawn criteria do not silently become a universal civil boundary."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo_waterclock import (
    source_specific_time_lines,
    source_specific_time_reference,
)

FIXTURE = Path(__file__).parent / "fixtures/sukuyo-daybreak-before-production-v75.json"


def test_new_source_layer_matches_entire_before_code_reference():
    expected = json.loads(FIXTURE.read_bytes())
    reference = source_specific_time_reference()["daybreak_source_comparison"]
    assert reference["source_data"] == expected["source_bundle"]
    assert (
        reference["conditional_unit_products"] == expected["expected"]["unit_products"]
    )
    assert reference["conditional_product_ratio"] == {"numerator": 10, "denominator": 1}
    assert reference["modern_seconds_before_sunrise"] is None


def test_full_native_text_delivers_source_layers_and_unresolved_mapping():
    text = "\n".join(source_specific_time_lines(source_specific_time_reference()))
    for phrase in (
        "五十",
        "300",
        "30",
        "掌文",
        "地色",
        "前二刻",
        "四分",
        "別宗",
        "定位小字",
    ):
        assert phrase in text
    assert "下之十五页码" not in text
    assert "未校成" in text and "出生换日" in text


@pytest.mark.parametrize(
    "change",
    [
        "fifty_to_five",
        "six_to_eight",
        "modern_seconds",
        "altitude",
        "half",
        "priority",
        "upstream",
        "missing_criterion",
        "renamed_source",
    ],
)
def test_corrupted_source_controls_are_rejected(change):
    from fatebridge.core.sukuyo_daybreak_criteria import validate_reference

    data = copy.deepcopy(json.loads(FIXTURE.read_bytes())["source_bundle"])
    if change == "fifty_to_five":
        data["unit_controls"]["X0744"]["muhurta_per_part"] = 5
    elif change == "six_to_eight":
        data["unit_controls"]["T2087"]["day_night_parts"] = 8
    elif change in {"modern_seconds", "altitude"}:
        data["scope"][
            (
                "modern_seconds_per_ke"
                if change == "modern_seconds"
                else "solar_altitude_degrees"
            )
        ] = (900 if change == "modern_seconds" else -6)
    elif change in {"half", "priority"}:
        data["scope"][
            (
                "hinoo_half_mapping_established"
                if change == "half"
                else "leap_short_month_priority_established"
            )
        ] = True
    elif change == "upstream":
        data["criteria"][1]["original_upstream_acquired"] = True
    elif change == "missing_criterion":
        data["criteria"].pop()
    else:
        data["sources"][0]["title"] = "法華經文句輔正記"
    with pytest.raises(ValueError):
        validate_reference(data)


def test_old_electronic_waterclock_bundle_not_rewritten():
    raw = (
        Path(__file__).parents[1] / "src/fatebridge/data/sukuyo_waterclock_sources.json"
    ).read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "affc2074b4e5a87d187035f94698cee595787a40322250812cd9132177521d37"
    )


def test_all_selected_apparatus_records_delivered_without_folding_layers():
    reference = source_specific_time_reference()["daybreak_source_comparison"]
    records = reference["selected_apparatus"]
    raw = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "5bd43e042fed4e54dd3350b54601767abc43698bac938c3bba8232badc9c8eba"
    )
    assert len(records["records"]) == 21
    assert {row["kind"] for row in records["records"]} == {"note", "app"}


def test_xml_layout_anchors_without_ids_do_not_hide_addressable_records():
    from xml.etree import ElementTree as E

    from scripts.check_sukuyo_daybreak import anchor_lines

    tree = E.fromstring(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><lb ed="T" n="1093b22"/><anchor type="circle"/><anchor xml:id="kept"/><lb ed="X" n="other"/><anchor type="circle"/></body></text></TEI>'
    )
    assert anchor_lines(tree, "T") == ({"kept": "1093b22"}, 2)


def test_native_attribution_delivers_headers_aliases_and_quoted_source_scope():
    reference = source_specific_time_reference()["daybreak_source_comparison"]
    header = reference["header_attribution"]
    raw = json.dumps(
        header, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "79e242b32714888cfebff413e0f2daf80245926054d7a472a7d573da5d6acb6d"
    )
    text = "\n".join(source_specific_time_lines(source_specific_time_reference()))
    for phrase in (
        "弘贊",
        "法雲",
        "失譯",
        "玄奘",
        "辯機",
        "阿樓那",
        "薩埵",
        "Aruṇa.",
        "通慧",
        "明了論",
        "十誦",
    ):
        assert phrase in text


def test_full_native_delivers_body_roles_and_unobtained_shisong_source():
    text = "\n".join(source_specific_time_lines(source_specific_time_reference()))
    for literal in (
        "弘麗羅峰校",
        "失譯人名今附秦錄",
        "三藏法師玄奘奉詔譯",
        "已取得《十誦律》",
        "完整原句尚未定位",
    ):
        assert literal in text
