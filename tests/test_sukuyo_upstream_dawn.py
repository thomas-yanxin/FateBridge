"""Direct upstream acquisition preserves the actual rule context and text layers."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo_waterclock import (
    source_specific_time_lines,
    source_specific_time_reference,
)

FIXTURE = Path(__file__).parent / "fixtures/sukuyo-upstream-before-production-v76.json"


def test_entire_source_first_reference_is_delivered():
    evidence = source_specific_time_reference()["daybreak_source_comparison"][
        "upstream_collation"
    ]
    assert evidence["source_data"] == json.loads(FIXTURE.read_bytes())["source_data"]
    assert evidence["baseline_acquisition_flags_describe_round"] == 75


def test_dawn_spans_are_literal_contextual_endpoints_not_clock_constants():
    evidence = source_specific_time_reference()["daybreak_source_comparison"][
        "upstream_collation"
    ]["source_data"]
    assert evidence["textual_spans"]["T1435_night"] == {
        "from_literal": "日沒",
        "to_literal": "地未了",
        "context": "比丘尼独宿戒释文",
    }
    assert evidence["textual_spans"]["T1435_day"] == {
        "from_literal": "地了",
        "to_literal": "日未沒",
        "context": "比丘尼独行戒释文",
    }
    assert evidence["scope"]["modern_seconds_per_ke"] is None
    assert not evidence["scope"]["birth_calendar_override_applied"]


def test_native_delivers_acquisition_without_asserting_transmission_or_priority():
    text = "\n".join(source_specific_time_lines(source_specific_time_reference()))
    for literal in (
        "安居五缘的第三项",
        "Aruṇuggamana.",
        "跨行",
        "已取得《十誦律》",
        "地未了",
        "日未沒",
        "行事鈔音義指歸三卷",
        "贊寧",
        "目录不是",
        "雨浴衣",
        "具足戒",
        "具体引本尚未认证",
    ):
        assert literal in text
    assert "这些上游原段本轮未直接取得。" not in text
    assert "未直接取得《十誦律》的对应上游段。" not in text


@pytest.mark.parametrize(
    "change",
    [
        "claim_quotation_identity",
        "catalog_as_body",
        "ground_definition",
        "seconds",
        "sun_altitude",
        "half",
        "priority",
        "age_rule",
        "unlabelled_legacy",
        "missing_window",
        "flatten_p_inline",
        "remove_foreign_note",
    ],
)
def test_corrupted_upstream_claims_or_layers_require_re_review(change):
    from fatebridge.core.sukuyo_upstream_dawn import validate_upstream_reference

    data = copy.deepcopy(json.loads(FIXTURE.read_bytes())["source_data"])
    if change == "claim_quotation_identity":
        data["acquisition"]["exact_X0744_T2131_quoted_exemplar_identified"] = True
    elif change == "catalog_as_body":
        data["acquisition"]["Zhigui_three_volume_body_acquired"] = True
    elif change == "ground_definition":
        data["acquisition"]["T1435_ground_color_definition_exact_located"] = True
    elif change == "seconds":
        data["scope"]["modern_seconds_per_ke"] = 900
    elif change == "sun_altitude":
        data["scope"]["solar_altitude_degrees"] = -6
    elif change == "half":
        data["scope"]["hinoo_half_mapping_established"] = True
    elif change == "priority":
        data["scope"]["leap_short_month_priority_established"] = True
    elif change == "age_rule":
        data["context_controls"][
            "ordination_fetal_leap_count_is_general_birth_age_rule"
        ] = True
    elif change == "unlabelled_legacy":
        data["id"] = "all_current_acquisition_flags"
    elif change == "missing_window":
        data["sources"][2]["windows"].pop("rain_leap")
    elif change == "flatten_p_inline":
        data["sources"][0]["windows"]["summer"]["body_blocks"] = []
    else:
        data["sources"][1]["all_selected_linked_postposed_records"] = []
    with pytest.raises(ValueError):
        validate_upstream_reference(data)


def test_aruna_exact_line_break_positions_are_delivered():
    reference = source_specific_time_reference()["daybreak_source_comparison"][
        "upstream_collation"
    ]["source_data"]
    source = next(s for s in reference["sources"] if s["id"] == "T1462")
    lines = source["windows"]["aruna"]["lines"]
    assert lines["0772a02"]["main"].endswith("阿")
    assert lines["0772a03"]["main"].startswith("留那出時")
    text = "\n".join(source_specific_time_lines(source_specific_time_reference()))
    assert "0772a02" in text and "0772a03" in text
