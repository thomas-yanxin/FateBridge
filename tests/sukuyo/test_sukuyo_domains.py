"""§7.7 Sukuyo oracles: T1299 fullmoon27, Sanjiu distances, Ryohan inversion, Kuyou, and budgets."""

from __future__ import annotations

import json
import time

import pytest

from fatebridge.core.local_techniques.suzhan import build_suzhan_result
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
