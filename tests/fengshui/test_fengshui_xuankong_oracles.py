"""XuanKong classical oracles: 432 Shen charts, triples, robbery, RuQiu, KongWang, city gate."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from fatebridge.core.fengshui.directions import MOUNTAINS_24
from fatebridge.core.fengshui.models import (
    Placement,
    XuankongInterpretationRequest,
    XuankongRequest,
)
from fatebridge.core.fengshui.xuankong import (
    _chart,
    analyze_natal_interpretation,
    xuankong_natal,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "shen-natal-source-comparison-v2.json"
)
OUTER_DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
KNOWN_SHEN_TYPOS = {
    ("lower", 7, "申", "寅", "E"),
    ("replacement", 5, "子", "午", "S"),
    ("replacement", 9, "坤", "艮", "S"),
}


def _natal_req(period: int, facing: float, **extra) -> XuankongRequest:
    return XuankongRequest.model_validate(
        {
            "house": {"facing_degrees": facing, "north_reference": "magnetic"},
            "period": {
                "basis": "expert_confirmed",
                "period_number": period,
                "evidence": "Oracle reference fixture",
            },
            **extra,
        }
    )


def test_all_432_shen_charts_against_frozen_edition_corpus() -> None:
    corpus = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(corpus["rows"]) == 216
    assert len(corpus["replacement_rows"]) == 216

    mountain_names = [m["name"] for m in MOUNTAINS_24]
    mismatches = []
    for mode, rows in (
        ("lower", corpus["rows"]),
        ("replacement", corpus["replacement_rows"]),
    ):
        for row in rows:
            period = row["period"]
            facing_idx = mountain_names.index(row["facing_mountain"])
            chart = _chart(period, (facing_idx, mode, "test"))
            assert chart["period_number"] == period
            assert chart["sitting"]["name"] == row["sitting_mountain"]
            assert chart["facing"]["name"] == row["facing_mountain"]
            for d, expected in row["diagram"]["palaces"].items():
                actual = chart["palaces"][d]
                if (
                    actual["period_star_number"] != expected["period"]
                    or actual["mountain_star_number"] != expected["mountain"]
                    or actual["facing_star_number"] != expected["facing"]
                ):
                    mismatches.append(
                        (
                            mode,
                            period,
                            row["sitting_mountain"],
                            row["facing_mountain"],
                            d,
                        )
                    )

    assert set(mismatches) == KNOWN_SHEN_TYPOS


def test_ti_gua_five_yellow_does_not_replace_oracle() -> None:
    # §6 #5: Period 7, 264.0° (酉兼庚, replacement)
    res = xuankong_natal(_natal_req(7, 264.0))
    assert res["status"] == "complete"
    chart = res["chart"]
    assert chart["chart_mode"] == "replacement"
    assert chart["facing"]["name"] == "酉"
    assert chart["sitting"]["name"] == "卯"
    assert chart["facing_subband"] == "jianxiang_replacement"
    assert chart["adjacent_mountain"] == "庚"
    # Sitting 卯(E) seed=5 borrows P7 heaven 酉(yin), flies 5 reverse without replacement
    m_trace = chart["trace"]["mountain"]
    assert m_trace["seed_star_number"] == 5
    assert m_trace["five_yellow_kept_without_replacement"] is True
    assert m_trace["center_star_number"] == 5
    assert m_trace["flight"] == "reverse"
    # Facing base[W]=9 -> 酉(9, yin reverse)
    f_trace = chart["trace"]["facing"]
    assert f_trace["seed_star_number"] == 9
    assert f_trace["center_star_number"] == 9
    assert f_trace["flight"] == "reverse"


def test_lianzhu_consecutive_triples_oracle() -> None:
    # §6 #1: Period 7, 150° (亥山巳向, lower) -> every palace is cyclic consecutive triple mod 9
    res = xuankong_natal(_natal_req(7, 150.0))
    chart = res["chart"]
    assert chart["sitting"]["name"] == "亥"
    assert chart["facing"]["name"] == "巳"
    assert chart["chart_mode"] == "lower"
    assert (
        chart["structure"]["classical_patterns"]["lianzhu_triples"]["all_nine_match"]
        is True
    )
    assert chart["palaces"]["C"]["period_star_number"] == 7
    assert chart["palaces"]["C"]["mountain_star_number"] == 8
    assert chart["palaces"]["C"]["facing_star_number"] == 6


def test_qixing_dajie_seven_stars_robbery_oracle() -> None:
    # §6 #2: Period 8, 225° (艮山坤向, lower)
    res = xuankong_natal(_natal_req(8, 225.0))
    chart = res["chart"]
    assert chart["sitting"]["name"] == "艮"
    assert chart["facing"]["name"] == "坤"
    patterns = chart["structure"]["classical_patterns"]
    assert patterns["parental_triples"]["all_nine_match"] is True
    robbery = patterns["qixing_dajie"]
    assert robbery["matched"] is True
    assert robbery["li_gong_dajie"]["matched"] is True
    assert robbery["li_gong_dajie"]["palace_triples"] == {
        "S": [3, 6, 9],
        "E": [6, 9, 3],
        "NW": [9, 3, 6],
    }
    assert robbery["kan_gong_dajie"]["matched"] is True
    assert robbery["kan_gong_dajie"]["palace_triples"] == {
        "N": [4, 7, 1],
        "SE": [7, 1, 4],
        "W": [1, 4, 7],
    }


def test_lingxing_ruqiu_and_eval_period_distribution_oracle() -> None:
    # §6 #3: Period 8, 150° (亥山巳向), current_period_number=9 -> mountain 9 in Center
    res_hai = xuankong_natal(_natal_req(8, 150.0, current_period_number=9))
    st = res_hai["chart"]["structure"]
    assert st["lingxing_ruqiu"]["lingxing_ruqiu"] is False
    assert st["eval_lingxing_ruqiu"]["mountain_in_center"] is True
    assert st["eval_lingxing_ruqiu"]["lingxing_ruqiu"] is True
    assert st["eval_period_distribution"]["eval_period_number"] == 9

    # Period 8, 330° (巳山亥向), current_period_number=9 -> facing 9 in Center
    res_si = xuankong_natal(_natal_req(8, 330.0, current_period_number=9))
    eval_rq = res_si["chart"]["structure"]["eval_lingxing_ruqiu"]
    assert eval_rq["facing_in_center"] is True
    assert eval_rq["lingxing_ruqiu"] is True


def test_kongwang_and_exact_dividing_line_candidates() -> None:
    # §6 #4: 22.5 -> da_kongwang; 37.5 -> yinyang_chacuo; 180.0 -> zhengxiang
    r22 = xuankong_natal(_natal_req(8, 22.5))
    assert r22["orientation_context"]["kongwang"] == "da_kongwang"
    assert len(r22["candidates"]) == 2
    assert r22["status"] == "partial"

    r37 = xuankong_natal(_natal_req(8, 37.5))
    assert r37["orientation_context"]["kongwang"] == "yinyang_chacuo"
    assert len(r37["candidates"]) == 2

    r180 = xuankong_natal(_natal_req(8, 180.0))
    assert r180["orientation_context"]["kongwang"] is None
    assert r180["orientation_context"]["facing_subband"] == "zhengxiang"
    assert r180["status"] == "complete"

    # Exact 64.5° dividing line produces [lower, replacement], while nextafter picks one
    assert (
        xuankong_natal(_natal_req(7, math.nextafter(64.5, -math.inf)))["chart"][
            "chart_mode"
        ]
        == "lower"
    )
    assert [
        c["chart_mode"] for c in xuankong_natal(_natal_req(7, 64.5))["candidates"]
    ] == ["lower", "replacement"]
    assert (
        xuankong_natal(_natal_req(7, math.nextafter(64.5, math.inf)))["chart"][
            "chart_mode"
        ]
        == "replacement"
    )


def test_city_gate_pure_geometric_complete_and_primary_secondary() -> None:
    res = xuankong_natal(
        _natal_req(
            8,
            180.0,
            city_gate={
                "reference_period_number": 9,
                "period_evidence": "Period 9 geometric gate query",
            },
        )
    )
    cg = res["city_gate_analysis"]
    assert cg["status"] == "complete"
    assert cg["missing_inputs"] == []
    gates = {g["direction"]: g for g in cg["candidates"][0]["gates"]}
    # Facing 午(S, 9): adjacent SE(4, 4-9 HeTu) = primary; SW(2) = secondary
    assert gates["SE"]["gate_type"] == "primary"
    assert gates["SE"]["gate_type_zh"] == "正城门"
    assert gates["SE"]["hetu_generation_pair"] is True
    assert gates["SW"]["gate_type"] == "secondary"
    assert gates["SW"]["gate_type_zh"] == "副城门"
    assert isinstance(gates["SE"]["usable"], bool)


def test_natal_interpretation_timeliness_host_guest_and_lingzheng() -> None:
    natal = xuankong_natal(_natal_req(8, 225.0))
    interp_req = XuankongInterpretationRequest.model_validate(
        {
            "current_period_number": 9,
            "period_evidence": "Period 9 evaluation",
            "timeliness_ruleset_id": "wang_zhongzhou_timeliness_v1",
            "host_guest_ruleset_id": "shen_2011_host_guest_v1",
            "fixed_lingzheng": {"observations": []},
            "external_forms": [
                {
                    "direction": d,
                    "mountain_present": False,
                    "water_present": False,
                    "observation_basis": "measured",
                    "evidence": f"{d} verified absent",
                }
                for d in OUTER_DIRECTIONS
            ],
        }
    )
    interp = analyze_natal_interpretation(
        interp_req,
        natal,
        [Placement(object_id="bed", purpose="bed", location_direction="N")],
    )
    assert interp["timeliness_ruleset_id"] == "wang_zhongzhou_timeliness_v1"
    assert interp["host_guest_analysis"]["status"] == "computed_relations"
    assert interp["fixed_lingzheng_analysis"]["candidates"][0]["zheng_direction"] == "S"
    assert interp["fixed_lingzheng_analysis"]["candidates"][0]["ling_direction"] == "N"
    assert interp["candidates"][0]["eval_lingxing_ruqiu"]["eval_period_number"] == 9
