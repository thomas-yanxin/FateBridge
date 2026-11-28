"""§7.7 Sukuyo oracles: T1299 fullmoon27, Sanjiu distances, Ryohan inversion, Kuyou, and budgets."""

from __future__ import annotations

import json
import time

import pytest

from fatebridge.core.sukuyo.calendar import (
    calendar_mansion,
    day_evidence,
    lunar_mansion,
)
from fatebridge.core.sukuyo.sanjiu import (
    assess_ryohan,
    kuyou_annual_star,
    kuyou_for_age,
    relation_between_su27,
)
from fatebridge.core.sukuyo.suzhan import build_suzhan_result
from fatebridge.services.divination import calculate_sukuyo_compatibility


@pytest.mark.parametrize(
    "month,day,expected",
    [(1, 15, "翼"), (1, 1, "室"), (2, 17, "氐"), (5, 5, "星"), (8, 15, "娄")],
)
def test_t1299_fullmoon27_oracles(month: int, day: int, expected: str) -> None:
    assert lunar_mansion(month, day) == expected


def test_sanjiu_distance_rules() -> None:
    sym = relation_between_su27("危", "觜", distance_rule="symmetric")
    assert sym["relation"] == "親"
    assert sym["pair"] == "栄親"
    assert sym["distance"] == "中距离"

    cyc = relation_between_su27("危", "觜", distance_rule="cyclic")
    assert cyc["pair"] == "栄親"
    assert cyc["distance"] == "近距离"

    none_rule = relation_between_su27("危", "觜", distance_rule="none")
    assert none_rule["pair"] == "栄親"
    assert none_rule["distance"] is None

    assert relation_between_su27("危", "危")["distance"] is None
    assert relation_between_su27("危", "参")["relation"] == "業"
    assert relation_between_su27("危", "参")["distance"] is None


def test_ryohan_and_special_day_inversion() -> None:
    hit = assess_ryohan(
        8, 15, "火", relation="栄", special_labels=("甘露", "罗刹"), urgent=False
    )
    assert hit["in_ryohan"] is True
    assert hit["relation_inverted"] is True
    assert hit["effective_assessment"] == "不可取用（反凶）"
    assert hit["special_days_inverted"] is True
    assert hit["inverted_special_labels"] == ["甘露"]

    urgent_hit = assess_ryohan(8, 15, "火", relation="壊", urgent=True)
    assert urgent_hit["in_ryohan"] is True
    assert urgent_hit["relation_inverted"] is True
    assert urgent_hit["effective_assessment"] == "急事可用（反吉）"

    miss = assess_ryohan(8, 28, "火", relation="栄", special_labels=("甘露",))
    assert miss["in_ryohan"] is False
    assert miss["relation_inverted"] is False
    assert miss["special_days_inverted"] is False


def test_kuyou_annual_star() -> None:
    assert [kuyou_for_age(i)["star"] for i in range(1, 10)] == [
        "羅睺星",
        "土曜星",
        "水曜星",
        "金曜星",
        "日曜星",
        "火曜星",
        "計都星",
        "月曜星",
        "木曜星",
    ]
    assert kuyou_annual_star(1990, 2024)["star"] == "月曜星"
    assert kuyou_annual_star(1990, 2025)["star"] == "木曜星"


def test_sukuyo_day_evidence_ryohan_and_kuyou_integration() -> None:
    ctx = calendar_mansion("2024-08-04", "09:00:00", "+08:00")
    ev = day_evidence(ctx, natal_mansion="危", birth_year=1990, target_year=2024)
    assert ev["day_mansion"] == "张"
    assert "ryohan" in ev
    assert ev["kuyou_annual"]["star"] == "月曜星"


def test_sukuyo_latency_and_audit_payload_budget() -> None:
    build_suzhan_result(date="2024-08-04", time="09:00:00", timezone="+08:00")
    t0 = time.perf_counter()
    res = build_suzhan_result(date="2024-08-04", time="09:00:00", timezone="+08:00")
    ms = (time.perf_counter() - t0) * 1000
    sz = len(json.dumps(res, ensure_ascii=False))
    assert ms < 15.0, f"Suzhan took {ms:.2f}ms >= 15ms"
    assert sz < 20 * 1024, f"Suzhan audit payload {sz}B >= 20KB"

    calculate_sukuyo_compatibility(
        person1_date="1990-06-15",
        person1_time="09:33:00",
        person1_zone="+08:00",
        person2_date="1992-08-20",
        person2_time="14:00:00",
        person2_zone="+08:00",
    )
    t1 = time.perf_counter()
    compat = calculate_sukuyo_compatibility(
        person1_date="1990-06-15",
        person1_time="09:33:00",
        person1_zone="+08:00",
        person2_date="1992-08-20",
        person2_time="14:00:00",
        person2_zone="+08:00",
    )
    ms2 = (time.perf_counter() - t1) * 1000
    sz2 = len(json.dumps(compat, ensure_ascii=False))
    assert ms2 < 15.0, f"Compat took {ms2:.2f}ms >= 15ms"
    assert sz2 < 20 * 1024, f"Compat audit payload {sz2}B >= 20KB"


def test_unknown_dates_explain_all_four_directed_relationship_rows() -> None:
    from fatebridge.services.divination import calculate_sukuyo_compatibility

    result = calculate_sukuyo_compatibility(
        person1_name="甲",
        person1_date="1346-07-17",
        person1_zone="+08:00",
        person2_name="乙",
        person2_date="1346-08-29",
        person2_zone="+08:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    assert result["pair"] is None
    rows = result["candidate_relation_analysis"]["rows"]
    assert {(r["person1_su27"], r["person2_su27"]) for r in rows} == {
        ("奎", "房"),
        ("奎", "心"),
        ("娄", "房"),
        ("娄", "心"),
    }
    assert all(not r["applied_to_primary"] for r in rows)


def test_unresolved_leap_candidate_and_declared_half_matrix() -> None:
    from fatebridge.services.divination import calculate_sukuyo_compatibility

    unresolved = calculate_sukuyo_compatibility(
        person1_date="2025-07-25",
        person1_zone="+08:00",
        person2_date="2025-03-04",
        person2_zone="+08:00",
    )
    assert not unresolved["candidate_relation_analysis"][
        "candidate_set_complete_within_profile"
    ]
    assert unresolved["pair"] is None

    declared = calculate_sukuyo_compatibility(
        person1_date="1341-05-24",
        person1_zone="+09:00",
        person2_date="1349-07-24",
        person2_zone="+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part="first_half",
        person2_calendar_day_part="first_half",
    )
    assert declared["pair"] is None
    assert set(declared["person1"]["calendar"]["candidate_su27s"]) == {"参", "毕"}
    assert set(declared["person2"]["calendar"]["candidate_su27s"]) == {"星", "鬼"}
    analysis = declared["candidate_relation_analysis"]
    assert len(analysis["rows"]) == 2
    assert len(analysis["unconstrained_rows"]) == 4
    assert analysis["shared_reconstruction_analysis"]["unsupported_row_count"] == 2


@pytest.mark.parametrize("civil", ["1346-08-30", "1346-08-29"])
def test_heart_source_restriction_is_retained_beside_general_favorable_day(
    civil: str,
) -> None:
    from fatebridge.core.sukuyo.calendar import calendar_mansion, day_evidence

    c = calendar_mansion(
        civil,
        time_text="23:30:00" if civil.endswith("29") else "12:00:00",
        zone="+08:00" if civil.endswith("29") else "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    d = day_evidence(c)
    assert d["day_mansion"] == "心" and d["activity_assessment"] is None
    assert "reading_text" not in d
    assert any(
        item["assessment"] == "favorable"
        for item in d["calendar_day"]["classifications"]
    )


@pytest.mark.parametrize("part", [None, "first_half"])
def test_unresolved_mansion_retains_candidate_list_and_palace(
    part: str | None,
) -> None:
    from fatebridge.core.sukuyo.calendar import calendar_mansion, day_evidence

    c = calendar_mansion(
        "1341-05-24",
        time_text="12:00:00",
        zone="+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part=part,
    )
    d = day_evidence(c)
    assert d["day_mansion"] is None and set(c["candidate_su27s"]) == {"参", "毕"}
    assert "reading_text" not in d
    assert d["palace_reference"]["mansion_candidates"] == ["参", "毕"]


def test_pair_structured_data_preserves_date_candidates_and_resolved_palace() -> None:
    from fatebridge.services.divination import calculate_sukuyo_compatibility

    r = calculate_sukuyo_compatibility(
        person1_name="甲",
        person1_date="1346-07-17",
        person1_zone="+08:00",
        person2_name="乙",
        person2_date="1346-08-29",
        person2_zone="+08:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    assert r["person2"]["palace_reference"]["selected_palace"]["name"] == "蝎宫"
    assert r["person1"]["calendar"]["date_support"]["utc_support_intervals"]
    assert r["person2"]["calendar"]["date_support"]["utc_support_intervals"]
    assert "candidate_relation_analysis" in r
