"""Printed month order, adverse readings and unsplit/actual result identities."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import month_table_variant
from fatebridge.core.sukuyo_koya import SOURCE, printed_month_reference
from fatebridge.core.sukuyo_profiles import select_profile
from fatebridge.core.sukuyo_sources import load_source
from scripts.check_sukuyo_koya import verify_printed

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/sukuyo-koya-1736-table.json").read_bytes()
)


def reference(month, day):
    selection = select_profile(
        month,
        day,
        False,
        SU27_ORDER,
        profile="t1299_fullmoon27",
        leap_policy="unresolved",
        day_part=None,
        previous_lunar=None,
    )
    host = selection["host_calculation"]
    return printed_month_reference(
        host, month_table_variant(month, day, host["direct_mansion"]), selection, False
    )


def test_all_360_literal_printed_cells_use_the_actual_february_to_january_order():
    assert FIXTURE["frozen_before_runtime_comparison"]
    assert FIXTURE["computed_cells"] == 0
    for day, literal in enumerate(FIXTURE["literal_day_columns"], 1):
        for slot, month in enumerate(FIXTURE["month_order"]):
            ref = reference(month, day)
            assert (
                ref["disputed_reading"]["root_literal"]
                if ref["disputed_reading"]
                else ref["printed_literal_mansion"]
            ) == literal[slot]
            assert ref["printed_locator"]["month_slot_from_top"] == slot + 1
            assert not ref["applied_to_primary"] and not ref["applied_to_sanjiu"]
    assert reference(1, 1)["printed_literal_mansion"] == "室"
    assert reference(2, 1)["printed_literal_mansion"] == "奎"


@pytest.mark.parametrize("day,taisho", [(3, "翼"), (30, "張")])
def test_adverse_readings_are_retained_in_three_named_identities(day, taisho):
    ref = reference(8, day)
    assert ref["printed_literal_mansion"] is None
    assert ref["candidate_literal_mansions"] == ["亢", "氐"]
    assert [r["matches_unsplit_host"] for r in ref["candidate_comparisons"]] == [
        False,
        True,
    ]
    assert ref["host_calculation"]["direct_mansion"] == "氐"
    assert ref["taisho_upper_table"]["literal_mansion"] == taisho
    assert ref["matches_unsplit_host"] is None
    assert not ref["complete_critical_edition_accepted"]


def test_full_audit_reports_both_mismatches_without_claiming_full_acceptance():
    report = verify_printed()
    assert report["printed_cells_compared"] == 360
    assert [(r["month"], r["day"]) for r in report["unresolved_readings"]] == [
        (8, 3),
        (8, 30),
    ]
    assert report["full_image_bytes_rechecked"] == []
    assert not report["full_critical_edition_accepted"]
    assert not report["original_domain_or_criteria_reduced"]


def test_changed_private_primary_bytes_are_rejected(tmp_path):
    (tmp_path / "upper-frame14.jpg").write_bytes(b"changed original image")
    with pytest.raises(ValueError, match="fingerprint changed"):
        verify_printed(tmp_path)


@pytest.mark.parametrize("part,actual", [("first_half", "星"), ("second_half", "张")])
def test_source_comparison_never_mislabels_half_assignment_as_unsplit_baseline(
    part, actual
):
    c = calendar_mansion(
        "2024-08-04", calendar_profile="hinoo_t1299_host27", calendar_day_part=part
    )
    assert c["natal_su27"] == actual
    assert c["source_table_variant"]["reference_month_day_mansion_27"] == "张"
    assert c["source_table_variant"]["reference_is_primary_result"] == (
        part == "second_half"
    )
    ref = c["printed_edition_reference"]
    assert ref["host_calculation"]["direct_mansion"] == "张"
    assert ref["printed_normalized_mansion"] == "张"
    assert ref["actual_profile_result"]["natal_su27"] == actual
    assert ref["matches_unsplit_host"]
    text = day_evidence(c)["reading_text"]
    assert "印字張" in text and "基准张" in text
    assert "不覆盖本次主宿" in text


def test_leap_precedence_and_unknown_half_candidates_survive_printed_agreement():
    c = calendar_mansion(
        "1903-06-25",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert c["natal_su27"] is None and c["candidate_su27s"] == ["鬼", "参"]
    ref = c["printed_edition_reference"]
    assert ref["actual_profile_result"]["candidate_su27s"] == ["鬼", "参"]
    assert ref["matches_unsplit_host"]
    assert not ref["source_reference"]["calendar_policy_evidence"][
        "leap_short_month_priority_established"
    ]
    assert not ref["source_reference"]["preface_selected_reference"][
        "operational_rule_accepted"
    ]


def test_each_unknown_date_candidate_keeps_its_own_printed_month_day_cell():
    c = calendar_mansion(
        "2024-08-04",
        zone="America/Los_Angeles",
        calendar_profile="hinoo_t1299_host27",
    )
    assert c["status"] == "partial"
    for branch in c["calendar_candidates"]:
        ref = branch["printed_edition_reference"]
        assert (ref["lunar_month"], ref["lunar_day"]) == (
            branch["lunar_month"],
            branch["lunar_day"],
        )
        assert (
            ref["actual_profile_result"]["candidate_su27s"] == branch["candidate_su27s"]
        )


def test_wrong_month_day_companion_rejected_and_result_detached():
    ref = reference(8, 3)
    expected = copy.deepcopy(ref)
    ref["printed_locator"]["printed_month_order"][0] = 1
    ref["source_reference"]["preface_selected_reference"][
        "operational_rule_accepted"
    ] = True
    assert reference(8, 3) == expected
    sel = select_profile(
        8,
        3,
        False,
        SU27_ORDER,
        profile="t1299_fullmoon27",
        leap_policy="unresolved",
        day_part=None,
        previous_lunar=None,
    )
    with pytest.raises(ValueError, match="月日不一致"):
        printed_month_reference(
            sel["host_calculation"], month_table_variant(8, 4, "氐"), sel, False
        )
    assert load_source(SOURCE).sha256 == expected["source_bundle_sha256"]


def test_loaded_source_snapshot_is_not_evicted_by_more_than_sixteen_other_tables(
    tmp_path,
):
    import hashlib

    p = tmp_path / "original.json"
    raw = b'{"id":"original"}'
    p.write_bytes(raw)
    first = load_source(p)
    for i in range(20):
        q = tmp_path / f"other-{i}.json"
        q.write_text(json.dumps({"id": i}))
        load_source(q)
    p.write_bytes(b'{"id":"replacement"}')
    second = load_source(p)
    assert second.data == first.data == {"id": "original"}
    assert second.sha256 == first.sha256 == hashlib.sha256(raw).hexdigest()
    assert second.sha256 != hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "first_date,second_date",
    [("2024-02-10", "2024-02-10"), ("2024-09-05", "2024-10-02")],
)
def test_resolved_default_compatibility_still_explains_material_printed_evidence(
    first_date, second_date
):
    from fatebridge.services.divination import calculate_sukuyo_compatibility

    result = calculate_sukuyo_compatibility(
        person1_date=first_date,
        person2_date=second_date,
        person1_zone="+08:00",
        person2_zone="+08:00",
    )
    assert result["status"] == "computed"
    text = result["summary"]
    assert "arcBK01-0086-01" in text
    assert "前向含义" in text and "反向含义" in text
    assert "亢／氐" in text and "不据此认证实物印刷年" in text
    assert "未分半基准" in text and "不覆盖本次主宿" in text


@pytest.mark.parametrize(
    "civil,activity,details",
    [
        ("2024-09-05", "travel", ["eastbound_journey"]),
        ("2024-10-02", "clothing", ["wearing_new_garments", "royal_wearer"]),
    ],
)
def test_native_preserves_missing_natal_layers_and_empty_directional_coverage(
    civil, activity, details
):
    from fatebridge.services.divination import calculate_suzhan_analysis

    result = calculate_suzhan_analysis(
        date=civil,
        time="12:00:00",
        zone="+08:00",
        activity=activity,
        activity_details=details,
    )
    day = result["sukuyo"]
    assert day["day_mansion"] == "氐"
    assert day["personal_day"] is None
    assert day["six_palace_reference"]["status"] == "natal_mansion_required"
    assert day["directional_travel"]["selected_records"] == []
    text = day["reading_text"]
    assert "未提供本命宿" in text and "个人三九日关系未计算" in text
    assert "六宫位置未计算" in text and "七曜运行犯宿未计算" in text
    assert "未找到已识别的氐宿方向条文" in text
    assert "互" in text and "未猜作氐" in text and "尾" in text
    if activity == "clothing":
        for literal in [
            "氐必覩友",
            "若用裁衣，多逢親識。",
            "教女人裁衣服",
            "初王者嚴服觀兵",
            "取衣取財",
        ]:
            assert literal in text
        assert "王者身份不能代替观兵条件" in text
        assert "未纳入事项汇总" in text and "不保证现实应验" in text


def test_native_historical_provenance_keeps_full_range_and_each_ordinal_anchor():
    from fatebridge.services.divination import calculate_sukuyo_compatibility

    result = calculate_sukuyo_compatibility(
        person1_name="甲",
        person2_name="乙",
        person1_date="1341-05-23",
        person2_date="1349-07-24",
        person1_zone="+08:00",
        person2_zone="+09:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_basis="japanese_naoj_historical_utc09",
        person2_calendar_day_part="first_half",
    )
    text = result["summary"]
    for token in [
        "0001-01-01",
        "1872-12-31",
        "453",
        "454",
        "210",
        "14",
        "489586",
        "489587",
        "492570",
        "-18",
        "庚申",
    ]:
        assert token in text
    assert "部分共用历史文献" in text
    assert "未列跨来源分歧记录" in text
    assert "不等于已获独立一致性验证" in text
    assert "不开放公历年零出生输入" in text
