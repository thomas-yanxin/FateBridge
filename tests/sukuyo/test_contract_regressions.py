"""Related contract regressions with shared imports; original cases retained."""

import copy
import json
from copy import deepcopy

import pytest

from fatebridge.core import sukuyo_commentarial_clock as clock
from fatebridge.core import sukuyo_general_days
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence
from fatebridge.core.sukuyo_documentary import clock_position_reference
from fatebridge.core.sukuyo_sources import LoadedSource
from fatebridge.core.sukuyo_special_days import special_day_evidence
from fatebridge.validation.sukuyo_semantic import semantic_calculation_view
from scripts.sukuyo.check_sukuyo_clock_position import verify_clock_position
from scripts.sukuyo.check_sukuyo_commentarial_clock import (
    check_literal_days,
    verify_primary,
)
from scripts.sukuyo.check_sukuyo_general_days import verify_general_days
from tests.sukuyo.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def test_sukuyo_clock_position_has_two_reciprocal_notes_for_one_operation():
    result = verify_clock_position()
    assert result["errors"] == [] and result["verified_cjk_counts"] == [248, 93]
    assert (
        result["paired_position_notes"] == 2
        and result["independent_position_operations"] == 1
    )
    reference = clock_position_reference()
    assert reference["adjacent_variant"]["base_literal"] == "一"
    assert reference["adjacent_variant"]["context_before_first_block_base"].endswith(
        "三方諸國一，"
    )
    assert reference["position_only_reconstruction"][
        "apparatus_indicated_block_order"
    ] == ["daybreak_eight_parts_93", "intervening_text", "lower_special_days_248"]
    assert not reference["position_only_reconstruction"]["full_ming_text_reconstructed"]


def test_sukuyo_clock_and_table_share_detached_position_evidence():
    first = calendar_day_evidence(1)["clock_doctrine"]["textual_position_reference"]
    second = special_day_evidence(
        "昴", 2, weekday_basis="modern_utc_plus08_civil_midnight"
    )["textual_position_reference"]
    assert first == second
    first["blocks"][0]["normalized_base_text"] = "changed"
    assert second == clock_position_reference()


@pytest.mark.parametrize(
    "date,primary,ming",
    [("2025-01-07", [], ["金刚峰"]), ("2025-04-22", ["金刚峰"], [])],
)
def test_sukuyo_lower_paragraph_position_does_not_replace_upper_weekday_variant(
    date, primary, ming
):
    day = day_evidence(calendar_mansion(date, "12:00:00"))
    special = day["special_day_evidence"]
    assert special["primary"]["matched_labels"] == primary
    assert (
        next(
            r for r in special["comparisons"] if r["witness"] == "upper_ming_apparatus"
        )["matched_labels"]
        == ming
    )
    assert not special["textual_position_reference"]["applied_to_primary_table"]
    assert day["calendar_day"]["clock_doctrine"]["day_parts"] == 8
    assert day["calendar_day"]["clock_doctrine"]["night_parts"] == 8


def test_sukuyo_position_does_not_fix_unidentified_lower_glyph_or_quoted_print():
    day = day_evidence(calendar_mansion("2025-01-09", "12:00:00"))
    lower = next(
        r
        for r in day["special_day_evidence"]["comparisons"]
        if r["witness"] == "lower_taisho"
    )
    assert lower["unresolved_rows"][0]["literal_mansion"] == "底"
    assert not lower["labels_complete_for_selected_day"]
    assert not day["calendar_day"]["clock_doctrine"]["textual_position_reference"][
        "position_only_reconstruction"
    ]["independent_ming_print_acquired"]


def test_sukuyo_position_does_not_resolve_hinoo_first_half_precedence():
    day = day_evidence(
        calendar_mansion(
            "1957-09-24",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
    )
    assert day["day_mansion"] is None
    assert day["calendar"]["candidate_su27s"] == ["角", "轸"]
    assert day["calendar_day"]["clock_evaluation_status"] == "not_computed"
    assert not day["special_day_evidence"]["textual_position_reference"][
        "leap_short_month_priority_established"
    ]


@pytest.mark.parametrize("kind", ["xml", "legend"])
def test_sukuyo_changed_position_source_is_rejected(tmp_path, kind):
    path = tmp_path / kind
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes changed"):
        verify_clock_position(
            **({"xml_path": path} if kind == "xml" else {"symbol_capture": path})
        )


def test_sukuyo_native_distinguishes_position_interchange_from_other_variant_types():
    text = day_evidence(calendar_mansion("2025-01-07", "12:00:00"))["reading_text"]
    assert "248字特殊日段" in text and "93字分时段" in text
    assert "一组位置异文，不是两个独立见证" in text
    assert "没有记八改六或删除分时段" in text
    assert "电子校记自身没有提供具名明本原页" in text
    assert "台大馆藏《永樂北藏》第一三〇册影印" in text
    assert "这不能认证它就是该校记所指的明本" in text


def test_all_twelve_literal_dates_keep_the_august_disagreement():
    result = clock.commentarial_boundary_reference()
    monthly = result["monthly_pushya_reference"]
    assert len(monthly["comparisons"]) == 12
    assert monthly["matching_controls"] == 11
    assert monthly["differing_controls"] == 1
    row = next(r for r in monthly["comparisons"] if not r["matches"])
    assert (row["lunar_month"], row["lunar_day"]) == (8, 23)
    assert row["quoted_mansion_literal"] == "補灑"
    assert row["normalized_quoted_mansion"] == "鬼" and row["host_mansion"] == "柳"
    assert not monthly["source_dates_changed_to_match_host"]
    assert not monthly["hinoo_half_or_leap_assignment_applied"]
    assert not monthly["quoted_work_independent_original_acquired"]


@pytest.mark.parametrize("mutation", ["duplicate", "omit", "boolean", "wrong_day"])
def test_literal_months_cannot_be_overwritten_or_silently_incomplete(
    monkeypatch, mutation
):
    loaded = clock.load_source(clock.SOURCE)
    source = loaded.data
    rows = source["monthly_pushya_reference"]["literal_days"]
    if mutation == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif mutation == "omit":
        rows.pop()
    elif mutation == "boolean":
        rows[0]["month"] = True
    else:
        rows[0]["day"] = 31
    monkeypatch.setattr(
        clock, "load_source", lambda _: LoadedSource(source, loaded.sha256)
    )
    with pytest.raises(ValueError, match="完整唯一且为合法整数"):
        clock.commentarial_boundary_reference()


def test_nested_day_boundary_accounts_and_white_eighth_condition_remain_distinct():
    result = clock.commentarial_boundary_reference()
    accounts = result["two_day_boundary_accounts"]
    assert [row["assigned_lunar_day"] for row in accounts["accounts"]] == [8, 9]
    assert not accounts["universal_boundary_established"]
    assert not accounts["mapped_to_modern_clock"]
    pair = result["second_month_eighth_ninth_comparison"]
    assert [row["direct_mansion"] for row in pair] == ["井", "鬼"]
    condition = result["white_eighth_pushya_condition"]
    assert condition["conditions"] == ["白月八日", "布灑／鬼星合"]
    assert not condition["all_white_eighth_days_assigned_pushya"]
    assert not condition["actual_lunar_conjunction_computed"]
    assert not condition["tithi_to_civil_date_mapping_established"]


def test_output_mutation_does_not_change_the_next_source_or_calculation():
    first = clock.commentarial_boundary_reference()
    first["monthly_pushya_reference"]["literal_days"][7]["day"] = 22
    first["monthly_pushya_reference"]["comparisons"][7]["host_mansion"] = "鬼"
    next_result = clock.commentarial_boundary_reference()
    assert next_result["monthly_pushya_reference"]["literal_days"][7]["day"] == 23
    assert (
        next_result["monthly_pushya_reference"]["comparisons"][7]["host_mansion"]
        == "柳"
    )


def test_reference_does_not_move_dates_or_choose_a_hinoo_precedence():
    current = calendar_mansion(
        "1903-06-25",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    before = copy.deepcopy(current)
    result = day_evidence(current)
    assert current == before
    assert result["calendar"]["candidate_su27s"] == ["鬼", "参"]
    assert result["day_mansion"] is None
    text = result["reading_text"]
    assert "8月23日原引補灑（鬼）／望宿柳" in text
    assert "11条相合、1条不同" in text
    assert "八月二十三原引日号保留" in text
    assert "二月八日为井、九日为鬼" in text
    assert "卯时以前仍属八日分" in text
    assert "不能将每月白八自动标为鬼宿" in text


def test_primary_checker_distinguishes_selected_text_from_originals():
    result = verify_primary()
    assert result["literal_month_day_controls"] == 12
    assert result["actual_capture_bytes_rechecked"] == []
    assert not result["all_three_actual_captures_rechecked"]
    assert not result["independent_manuscript_collation"]
    assert not result["historical_clock_mapping_established"]


@pytest.mark.parametrize("changed", ["control", "quotation"])
def test_source_quotation_and_executable_date_controls_cannot_drift_apart(changed):
    source = clock.load_source(clock.SOURCE).data
    if changed == "control":
        source["monthly_pushya_reference"]["literal_days"][7]["day"] = 22
    else:
        source["sources"][0]["selected_quotations"][0]["literal"] = source["sources"][
            0
        ]["selected_quotations"][0]["literal"].replace("八月二十三日", "八月二十二日")
    with pytest.raises(ValueError, match="未绑定所选原引日号"):
        check_literal_days(source)


@pytest.mark.parametrize("name", ["T2216", "T1788", "T0665"])
def test_primary_checker_rejects_substituted_actual_source_bytes(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"replaced")
    with pytest.raises(ValueError, match="字节指纹不一致"):
        verify_primary({name: path})


@pytest.mark.parametrize("date", ["2024-03-17", "2024-09-25"])
def test_new_reference_across_actual_rest_native_mcp_and_cli(monkeypatch, capsys, date):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {"date": date, "time": "04:30:00", "zone": "+08:00"},
        [
            "sukuyo.calendar_day.clock_doctrine.commentarial_boundary_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )


def test_prose_enumerations_check_all_sixty_classifications_and_paragraphs():
    report = verify_general_days()
    assert report["errors"] == []
    assert report["day_classifications_checked"] == 60
    assert report["selected_paragraphs_checked"] == 6


def test_whole_comparison_retains_both_sources_and_the_direction_of_differences():
    for day in (1, 9, 10, 16, 24, 25, 30):
        result = calendar_day_evidence(day)
        comparison = result["japanese_selected_reference"]
        reference = comparison["primary_general_day_reference"]
        assert [row["witness"] for row in reference["witnesses"]] == [
            "upper_prose",
            "lower_prose",
        ]
        for full, current, difference in zip(
            reference["witnesses"],
            comparison["primary_general_day_comparison"],
            comparison["full_favorable_membership_comparison"],
            strict=True,
        ):
            assert len(full["all_thirty_classifications"]) == 30
            assert (
                full["all_thirty_classifications"][day - 1]["assessment"]
                == current["primary_assessment"]
            )
            assert difference["primary_only_days"] == [10, 16, 25]
            assert difference["body_only_days"] == [9, 24]
            assert difference["symmetric_difference_days"] == [9, 10, 16, 24, 25]
            assert not difference["applied_to_primary_or_activities"]


def test_native_whole_list_comparison_follows_each_returned_witness(
    tmp_path, monkeypatch
):
    # Change only the upper source in a temporary file. A static five-day
    # sentence would now contradict its own current classification and list.
    data = json.loads(sukuyo_general_days.SOURCE.read_text())
    data["witnesses"][0]["favorable_lunar_days"].remove(10)
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(sukuyo_general_days, "SOURCE", altered)
    result = day_evidence(calendar_mansion("2024-06-15", "06:30:00"))
    text = result["reading_text"]
    assert "上卷散文一般吉日名单的差别为9、16、24、25日" in text
    assert "下卷散文一般吉日名单的差别为9、10、16、24、25日" in text
    assert result["calendar_day"]["classifications"][0]["assessment"] == "unlisted"
    assert verify_general_days()["errors"] == [
        ["upper_prose", "favorable_list"],
        ["upper_prose", 10, "classification"],
    ]


def test_general_day_reference_is_detached_and_invalid_days_are_rejected():
    first = sukuyo_general_days.general_day_evidence(10)
    original = deepcopy(first)
    first["reference"]["witnesses"][0]["favorable_lunar_days"].clear()
    first["reference"]["witnesses"][0]["all_thirty_classifications"][9][
        "assessment"
    ] = "unlisted"
    assert sukuyo_general_days.general_day_evidence(10) == original
    for day in (0, 31, True, 1.0, "1"):
        with pytest.raises(ValueError):
            sukuyo_general_days.general_day_evidence(day)


def test_primary_checker_rejects_changed_full_source(tmp_path):
    path = tmp_path / "changed.xml"
    path.write_text("changed")
    with pytest.raises(ValueError, match="full source bytes changed"):
        verify_general_days(path)


@pytest.mark.parametrize("date", ["2025-02-02", "2025-02-08"])
def test_sukuyo_new_printed_clock_witness_is_delivered_with_its_actual_conditions(date):
    result = day_evidence(calendar_mansion(date, "12:00:00"))
    doctrine = result["calendar_day"]["clock_doctrine"]
    ref = doctrine["kenyu_printed_reference"]
    assert ref["condition_day_luminary"] == result["weekday"]["luminary"]
    assert ref["condition_weekday_basis"] == result["weekday"]["basis"]
    assert ref["selected_hour_luminary"] is None
    assert ref["selected_branch"] is None
    assert not ref["civil_time_used_to_select_branch"]
    assert result["calendar_day"]["clock_evaluation_status"] == "not_computed"
    assert doctrine["intradaily_luminary_order"] is None
    assert doctrine["day_parts"] == doctrine["night_parts"] == 8
    text = result["reading_text"]
    assert "日曜直日午时当水曜" in text
    assert "土曜直日寅时上金下土" in text
    assert "夜分上下两项不等同桧尾初一前后半" in text
    assert "潤月朔宿全如本月" in text


@pytest.mark.parametrize(
    "weekday,expected",
    [
        ("日", "日月火水木金土日"),
        ("月", "月火水木金土日月"),
        ("火", "火水木金土日月火"),
        ("水", "水木金土日月火水"),
        ("木", "木金土日月火水木"),
        ("金", "金土日月火水木金"),
        ("土", "土日月火水木金土"),
    ],
)
def test_sukuyo_printed_columns_and_night_row_pairing(weekday, expected):
    from fatebridge.core.sukuyo_kenyu import lookup_printed_hour

    # Independent visual column transcription, not values generated by lookup.
    day = [lookup_printed_hour(weekday, branch) for branch in "卯辰巳午未申酉戌"]
    night = [lookup_printed_hour(weekday, branch) for branch in "亥子丑寅"]
    assert "".join(row["selected_hour_luminary"] for row in day) == expected
    assert "".join(r["hour_luminary"] for row in night for r in row["rows"]) == expected
    assert all(row["selected_hour_luminary"] is None for row in night)
    assert [r["row_one_based"] for row in night for r in row["rows"]] == list(
        range(1, 9)
    )


def test_sukuyo_prose_examples_and_night_reset_are_not_western_horas():
    from fatebridge.core.sukuyo_kenyu import lookup_printed_hour

    assert lookup_printed_hour("日", "午")["selected_hour_luminary"] == "水"
    assert lookup_printed_hour("土", "寅", "upper")["selected_hour_luminary"] == "金"
    assert lookup_printed_hour("土", "寅", "lower")["selected_hour_luminary"] == "土"
    assert [r["hour_luminary"] for r in lookup_printed_hour("日", "亥")["rows"]] == [
        "日",
        "月",
    ]
    assert lookup_printed_hour("日", "戌")["selected_hour_luminary"] == "日"
    assert not lookup_printed_hour("土", "寅", "upper")[
        "hinoo_half_mapping_established"
    ]


@pytest.mark.parametrize(
    "args",
    [
        ("太阳", "午"),
        ("日", "12:00"),
        ("日", "午", "upper"),
        ("土", "寅", "first_half"),
    ],
)
def test_sukuyo_civil_hours_and_hinoo_half_aliases_cannot_select_printed_slot(args):
    from fatebridge.core.sukuyo_kenyu import lookup_printed_hour

    with pytest.raises(ValueError):
        lookup_printed_hour(*args)


def test_sukuyo_new_witness_does_not_resolve_leap_short_month_or_change_candidates():
    result = day_evidence(
        calendar_mansion(
            "1957-09-24",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
    )
    ref = result["calendar_day"]["clock_doctrine"]["kenyu_printed_reference"]
    assert result["day_mansion"] is None
    assert result["calendar"]["candidate_su27s"] == ["角", "轸"]
    assert not ref["calendar_selected"]["leap_short_month_priority_established"]
    assert not ref["applied_to_primary_or_activities"]
    assert not ref["physical_clock_mapping_established"]


def test_sukuyo_printed_reference_is_detached_and_known_clock_is_not_an_input():
    from fatebridge.core.sukuyo_kenyu import printed_clock_reference

    result = printed_clock_reference("日", "modern_utc_plus08_civil_midnight")
    result["conditional_branch_readings"][0]["rows"][0]["hour_luminary"] = "changed"
    result["clock_selected"]["table_rows"][0]["luminaries"][0] = "changed"
    fresh = printed_clock_reference("日", "modern_utc_plus08_civil_midnight")
    assert fresh["conditional_branch_readings"][0]["rows"][0]["hour_luminary"] == "日"
    first = day_evidence(calendar_mansion("2025-02-02", "00:01:00"))
    last = day_evidence(calendar_mansion("2025-02-02", "23:59:00"))
    assert (
        first["calendar_day"]["clock_doctrine"]["kenyu_printed_reference"]
        == last["calendar_day"]["clock_doctrine"]["kenyu_printed_reference"]
    )


def test_sukuyo_schema_publishes_the_printed_companion():
    from fatebridge.services.tool_catalog import CATALOG

    spec = next(s for s in CATALOG if s.key == "suzhan")
    defs = spec.output_model.model_json_schema()["$defs"]
    assert "kenyu_printed_reference" in defs["SukuyoClockDoctrine"]["properties"]


def test_sukuyo_primary_checker_distinguishes_cached_table_from_actual_captures(
    tmp_path,
):
    from scripts.sukuyo.check_sukuyo_kenyu import verify_kenyu

    cached = verify_kenyu()
    assert not cached["captured_bytes_rechecked"]
    assert cached["printed_cells"] == 56
    assert cached["explicit_prose_lookups"] == 3
    assert not cached["modern_clock_conversion_established"]
    (tmp_path / "nijl-100159236-manifest.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Captured source bytes changed"):
        verify_kenyu(tmp_path)


def test_sukuyo_lingbi_table_is_exposed_without_replacing_primary_results():
    result = day_evidence(calendar_mansion("2025-02-01", "12:00:00"), "室", "study")
    reference = result["kenyu_lingbi_reference"]
    assert reference["source_image"]["frame"] == 8
    assert len(reference["printed_rows"]) == 23
    assert reference["t1299_planetary_condition_evaluated"] is False
    assert reference["applied_to_primary_or_activities"] is False
    assert reference["ancient_day_boundary_established"] is False
    assert "若有急事欲作之者" in result["reading_text"]
    assert "月首曜条件" in result["reading_text"]


def test_sukuyo_lingbi_literal_endpoints_and_unlisted_conditions_are_preserved():
    from fatebridge.core.sukuyo_kenyu_lingbi import lookup_lingbi_interval

    assert lookup_lingbi_interval(7, "金", 3)["membership_in_printed_interval"] is True
    assert lookup_lingbi_interval(7, "金", 4)["membership_in_printed_interval"] is False
    assert (
        lookup_lingbi_interval(12, "金", 30)["membership_in_printed_interval"] is True
    )
    unlisted = lookup_lingbi_interval(8, "日", 28)
    assert unlisted["matching_intervals"] == []
    assert unlisted["membership_in_printed_interval"] is None
    assert lookup_lingbi_interval(8, "火", 27)["membership_in_printed_interval"] is True
    assert (
        lookup_lingbi_interval(8, "火", 28)["membership_in_printed_interval"] is False
    )


def test_sukuyo_period_lookup_uses_the_month_start_ruler_not_the_current_day_ruler():
    result = day_evidence(calendar_mansion("2024-02-11", "06:30:00"))
    reference = result["kenyu_lingbi_reference"]
    assert result["weekday"]["luminary"] == "日"
    assert reference["civil_month_start_reference"]["date"] == "2024-02-10"
    selected = reference["selected_civil_month_start_lookup"]
    assert selected["condition_month_start_luminary"] == "土"
    assert selected["condition_lunar_day"] == 2
    assert selected["membership_in_printed_interval"] is True
    assert not reference["applied_to_primary_or_activities"]


def test_sukuyo_lingbi_condition_and_urgent_clause_do_not_contaminate_cached_source():
    result = day_evidence(calendar_mansion("2024-02-11"), "室", "study")
    reference = result["kenyu_lingbi_reference"]
    assert reference["urgent_action_established"] is None
    assert next(r for r in reference["personal_conditions"] if "危" in r["relations"])[
        "urgent_action_required"
    ]
    reference["printed_rows"].clear()
    assert (
        len(
            day_evidence(calendar_mansion("2024-02-11"))["kenyu_lingbi_reference"][
                "printed_rows"
            ]
        )
        == 23
    )


def test_sukuyo_new_reference_keeps_independent_day_facts_when_month_is_unknown():
    minimal = {
        "natal_su27": "参",
        "calendar_date": "2025-03-04",
        "calendar_timezone": "UTC+08:00",
        "lunar_day": 7,
    }
    result = day_evidence(
        minimal, activity="travel", activity_details=["long_distance_journey"]
    )
    reference = result["kenyu_lingbi_reference"]
    assert result["day_mansion"] == "参"
    assert result["activity_assessment"] is not None
    assert reference["lookup_status"] == "not_evaluated_missing_calendar_context"
    assert reference["missing_context_fields"] == ["lunar_month", "is_leap_month"]
    assert reference["selected_civil_month_start_lookup"] is None
    assert len(reference["printed_rows"]) == 23
    assert minimal.get("lunar_month") is None


def test_sukuyo_lingbi_leap_clause_does_not_decide_hinoo_priority_or_daybreak():
    result = day_evidence(
        calendar_mansion(
            "1903-06-25",
            "06:00:00",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
    )
    reference = result["kenyu_lingbi_reference"]
    assert reference["leap_month_reference"]["literal"] == "潤月全如本月"
    assert reference["selected_civil_month_start_lookup"] is None
    assert (
        reference["leap_month_reference"]["month_start_ruler_inheritance_established"]
        is False
    )
    assert len(reference["conditional_month_start_lookups"]) == 7
    assert result["day_mansion"] is None
    assert set(result["calendar"]["candidate_su27s"]) == {"鬼", "参"}
    assert result["calendar_day"]["clock_evaluation_status"] == "not_computed"


@pytest.mark.parametrize(
    "args", [(True, "日", 1), (13, "日", 1), (1, "太阳", 1), (1, "日", 31)]
)
def test_sukuyo_lingbi_lookup_refuses_invalid_conditions(args):
    from fatebridge.core.sukuyo_kenyu_lingbi import lookup_lingbi_interval

    with pytest.raises(ValueError):
        lookup_lingbi_interval(*args)


@pytest.mark.parametrize(
    "date,known_inside,known_outside,unknown_count",
    [("1957-09-24", "火", None, 6), ("1903-06-25", "日", "月", 5)],
)
def test_native_leap_month_delivers_all_conditions_without_selecting_one(
    date, known_inside, known_outside, unknown_count
):
    day = day_evidence(
        calendar_mansion(
            date,
            "06:30:00",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        ),
        "角",
        "travel",
    )
    reference = day["kenyu_lingbi_reference"]
    text = day["reading_text"]
    assert reference["selected_civil_month_start_lookup"] is None
    assert len(reference["conditional_month_start_lookups"]) == 7
    assert text.count("本月未列，成员判断未定") == unknown_count
    assert f"若月首{known_inside}曜，表列" in text and "本日在内" in text
    if known_outside:
        assert f"若月首{known_outside}曜，表列" in text and "本日在外" in text
    for condition in reference["conditional_month_start_lookups"]:
        assert f"若月首{condition['condition_month_start_luminary']}曜" in text
        for interval in condition["matching_intervals"]:
            assert interval["literal"] in text
    assert not reference["applied_to_primary_or_activities"]
    assert day["day_mansion"] is None


@pytest.mark.parametrize("zone", ["+14:00", "America/New_York"])
def test_native_unknown_clock_explains_every_support_interval_without_imputation(zone):
    day = day_evidence(
        calendar_mansion("2024-02-11", zone=zone),
        "角",
        "clothing",
        ["wearing_new_garments"],
    )
    support = day["calendar"]["date_support"]
    assert not support["birth_time_imputed"]
    assert len(day["candidate_days"]) >= 2
    for row in support["utc_support_intervals"]:
        expected = (
            f"参考历日{row['calendar_date']}由UTC区间"
            f"[{row['start_utc_inclusive']}, {row['end_utc_exclusive']})支持。"
        )
        assert expected in day["reading_text"]
    assert "不是实际出生时刻或概率" in day["reading_text"]
    assert day["day_mansion"] is None


def test_native_named_peak_keeps_its_specific_meaning_and_learning_uncovered():
    day = day_evidence(
        calendar_mansion("2025-04-14", "06:30:00"),
        "室",
        "study",
        ["religious_learning"],
    )
    assert day["special_day_evidence"]["primary"]["matched_labels"] == ["金刚峰"]
    assert day["activity_assessment"]["evidence_status"] == "uncovered"
    assert "金刚峰标签的传统词义另参考下卷大正" in day["reading_text"]
    assert "降伏法" in day["reading_text"] and "作護摩" in day["reading_text"]
    assert "未声称其他印本说明全文相同" in day["reading_text"]


def test_native_candidate_nectar_is_not_called_an_empty_match_or_selected():
    day = day_evidence(
        calendar_mansion(
            "1903-06-25",
            "03:20:00",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        ),
        "室",
        "commerce",
    )
    candidate = day["special_day_evidence"]["candidate_primary"][0]
    assert candidate["mansion"] == "鬼" and candidate["matched_labels"] == ["甘露"]
    assert "不以该支空匹配" not in day["reading_text"]
    assert "甘露标签的传统词义另参考下卷大正" in day["reading_text"]
    assert "受灌頂法" in day["reading_text"] and "習學經法" in day["reading_text"]
    assert day["day_mansion"] is None


def test_pair_export_copies_are_removed_while_all_candidate_relations_survive():
    source = {
        "reading_text": "NATIVE-ANSWER",
        "summary": "NATIVE-ANSWER",
        "snapshot_export": {
            "sections": [{"content": "NATIVE-ANSWER"}],
            "export_text": "NATIVE-ANSWER",
        },
        "snapshot_text": "NATIVE-ANSWER",
        "export_text": "NATIVE-ANSWER",
        "run_metadata": {"run_id": "metadata"},
        "person1": {"calendar_candidates": [{"day": 20}, {"day": 21}]},
        "person2": {"candidate_su27s": ["参", "毕"]},
        "pair": None,
        "candidate_relation_analysis": {
            "complete": False,
            "rows": [
                {"direction": "a_to_b", "role": "危"},
                {"direction": "b_to_a", "role": "成"},
            ],
        },
        "rulesets": {"source_passages": [{"text": "SOURCE-TEXT"}]},
        "validation": {"real_samples": 0},
        "future_domain_field": {"unfavorable_result": True},
    }
    before = deepcopy(source)
    view = semantic_calculation_view("sukuyo_compatibility", source)
    assert "NATIVE-ANSWER" not in str(view)
    assert set(view) == set(source) - {
        "reading_text",
        "summary",
        "snapshot_export",
        "snapshot_text",
        "export_text",
        "run_metadata",
    }
    assert view["candidate_relation_analysis"] == source["candidate_relation_analysis"]
    assert view["rulesets"] == source["rulesets"]
    assert view["future_domain_field"] == source["future_domain_field"]
    view["person1"]["calendar_candidates"].clear()
    assert source == before


def test_suzhan_projection_removes_nested_native_text_and_keeps_source_conditions():
    source = {
        "params": {"calendar_day_part": "first_half"},
        "sukuyo": {
            "reading_text": "NATIVE-ANSWER",
            "candidate_days": [
                {
                    "reading_text": "OTHER-NATIVE",
                    "source_passages": [{"text": "SOURCE-TEXT", "conditional": True}],
                }
            ],
        },
        "rulesets": {"unresolved": ["leap_priority"]},
        "snapshot_export": {"export_text": "NATIVE-ANSWER"},
        "physical_chart": {"evaluated_separately": True},
    }
    view = semantic_calculation_view("suzhan", source)
    assert "NATIVE" not in str(view)
    assert view["sukuyo"]["candidate_days"][0]["source_passages"] == [
        {"text": "SOURCE-TEXT", "conditional": True}
    ]
    assert view["params"] == source["params"] and view["rulesets"] == source["rulesets"]
    assert set(view) == {"params", "sukuyo", "rulesets"}
    assert source["sukuyo"]["reading_text"] == "NATIVE-ANSWER"


def test_unknown_tool_or_missing_required_suzhan_evidence_is_rejected():
    with pytest.raises(ValueError):
        semantic_calculation_view("other", {})
    with pytest.raises(KeyError):
        semantic_calculation_view("suzhan", {"params": {}, "rulesets": {}})
