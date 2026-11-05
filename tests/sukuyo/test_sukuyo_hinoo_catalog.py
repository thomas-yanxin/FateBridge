"""A catalogue hit is neither a manuscript reading nor an independent event."""

import hashlib
import json
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_hinoo_catalog import (
    SOURCE,
    catalogue_reference,
    validate_bundle,
)
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.services.divination import calculate_sukuyo_compatibility

NOTE = "＜原＞建久六年寫高山寺藏本, ＜甲＞寶暦十一年寫智山專門學校藏本"


def test_complete_catalogue_facts_match_before_production_source_snapshot():
    raw = (
        Path(__file__).parents[1] / "data/sukuyo-hinoo-catalogue-source-v1.json"
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "cccfed4983475f02164adc60b9f993c0e290c71c9dc769f89d053a91c16a2b18"
    )
    expected = json.loads(raw)
    ref = catalogue_reference(NOTE)
    assert ref["facts"] == expected
    assert ref["before_code_facts_sha256"] == hashlib.sha256(raw).hexdigest()
    hinoo = ref["facts"]["kozanji_hinoo_search"]
    grouped = defaultdict(list)
    for row in hinoo["complete_returned_records"]:
        grouped[row["sec"], row.get("bxnum"), row["bknum"]].append(row["id"])
    assert len(hinoo["complete_returned_records"]) == 8
    assert len(grouped) == 5
    assert grouped["4", "079", "085"] == ["7131", "7132", "7133", "7134"]
    assert set(grouped["4", "084", "001"]) == {"7744"}
    assert (
        len(ref["facts"]["kozanji_shukuyo_search"]["complete_returned_records"]) == 11
    )
    assert not hinoo["named_base_description_candidate"][
        "same_physical_item_as_taisho_original_certified"
    ]
    assert not hinoo["named_base_description_candidate"][
        "same_as_taisho_ko_witness_certified"
    ]
    ref["facts"]["kozanji_hinoo_search"]["catalogue_group_count"] = 8
    assert (
        catalogue_reference(NOTE)["facts"]["kozanji_hinoo_search"][
            "catalogue_group_count"
        ]
        == 5
    )


@pytest.mark.parametrize(
    "note",
    [
        "＜原＞寶暦十一年寫智山專門學校藏本, ＜甲＞建久六年寫高山寺藏本",
        NOTE.replace("六年", "四年"),
        NOTE.replace("智山專門學校", "大正大学"),
    ],
)
def test_catalogue_candidate_cannot_be_inherited_by_another_publisher_note(note):
    with pytest.raises(ValueError, match="书目注不一致"):
        catalogue_reference(note)


@pytest.mark.parametrize(
    "mutation",
    [
        "count",
        "dropped_wrapper",
        "base_identity",
        "ko_identity",
        "portal_absence",
        "text",
        "real",
    ],
)
def test_candidate_or_negative_search_cannot_silently_become_an_acquired_witness(
    mutation,
):
    data = deepcopy(load_source(SOURCE).data)
    facts = data["facts"]
    hinoo = facts["kozanji_hinoo_search"]
    if mutation == "count":
        hinoo["catalogue_group_count"] = 8
    elif mutation == "dropped_wrapper":
        hinoo["complete_returned_records"].pop(1)
    elif mutation == "base_identity":
        hinoo["named_base_description_candidate"][
            "same_physical_item_as_taisho_original_certified"
        ] = True
    elif mutation == "ko_identity":
        hinoo["named_base_description_candidate"][
            "same_as_taisho_ko_witness_certified"
        ] = True
    elif mutation == "portal_absence":
        facts["taisho_portal_keyword_searches"][0][
            "current_holdings_or_digitization_absence_proven"
        ] = True
    elif mutation == "text":
        facts["kozanji_shukuyo_search"][
            "contents_or_priority_read_from_titles_only"
        ] = True
    else:
        facts["acceptance_status"]["real_samples"] = 1
    with pytest.raises(ValueError):
        validate_bundle(data)


@pytest.mark.parametrize("civil", ["0806-07-20", "0814-09-17"])
def test_hinoo_product_retains_real_result_and_catalogue_limits(civil):
    calendar = calendar_mansion(
        civil,
        "12:00:00",
        "+09:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    ref = calendar["profile_calculation"]["hinoo_source"][
        "critical_calendar_reference"
    ]["witness_catalogue_candidates"]
    assert (
        ref["facts"]["acceptance_status"]["calendar_or_mansion_values_changed"] is False
    )
    assert calendar["calendar_day_part"] is None
    text = day_evidence(calendar)["reading_text"]
    for part in [
        "8条记录、5个目录组",
        "不是8部独立写本",
        "未取得该件原图",
        "与高雄口決",
        "檜尾与桧尾均0命中",
        "不证明学校没有该书",
        "第十八轮已保存",
        "未新增这些候选的正文影像",
        "真实预测样本0",
    ]:
        assert part in text


def test_catalogue_extension_does_not_select_hinoo_for_default_t1299_profile():
    calendar = calendar_mansion(
        "0806-07-20",
        "12:00:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    assert calendar["calendar_profile"] != "hinoo_t1299_host27"
    # The pre-existing public contract keeps this key explicitly null.
    assert calendar["profile_calculation"]["hinoo_source"] is None


@pytest.mark.parametrize("part", [None, "first_half", "second_half"])
def test_no_split_still_explains_actual_big_leap_predecessor(part):
    calendar = calendar_mansion(
        "0803-12-22",
        "04:00:00",
        "+09:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_day_part=part,
    )
    before = deepcopy(calendar)
    text = day_evidence(calendar)["reading_text"]
    assert calendar == before
    assert calendar["profile_calculation"]["short_month_assignment"] is None
    assert calendar["natal_su27"] == "斗"
    assert calendar["candidate_su27s"] == []
    assert "前一参考日为0803-12-21，农历803年闰10月30日" in text
    assert "相邻前月为30日大闰月" in text
    assert "前月没有缺失第三十日" in text
    assert "本次未生成小月分宿" in text


def test_no_split_explanation_does_not_invent_context_on_a_later_day():
    calendar = calendar_mansion(
        "0803-12-23",
        "04:00:00",
        "+09:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    text = day_evidence(calendar)["reading_text"]
    assert calendar["lunar_day"] == 2
    assert "本次初一所用前一参考日" not in text


@pytest.mark.parametrize("part", [None, "first_half", "second_half"])
def test_two_person_explanation_keeps_big_leap_predecessor_for_resolved_person(part):
    result = calculate_sukuyo_compatibility(
        person1_date="0803-12-22",
        person1_time="04:00:00",
        person1_zone="+09:00",
        person1_calendar_day_part=part,
        person2_date="0806-07-23",
        person2_time="05:45:00",
        person2_zone="+09:00",
        person2_calendar_day_part="first_half",
        calendar_profile="hinoo_t1299_host27",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    text = result["summary"]
    assert "前一参考日为0803-12-21，农历803年闰10月30日" in text
    assert "相邻前月为30日大闰月" in text
    assert "前月没有缺失第三十日" in text
    if part is None:
        assert "甲方原典半日未声明" in text
    else:
        assert f"甲方原典{'前半' if part == 'first_half' else '后半'}已声明" in text
