"""Independent numeric facts, event provenance and ambiguous compass limits."""

import json
import math
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import almanac
from fatebridge.core.fengshui.calendar import lichun
from fatebridge.core.fengshui.directions import bearing_context, sitting_from_facing
from fatebridge.core.fengshui.models import HousePeriod, XuankongRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.core.fengshui.xuankong import (
    _selectors,
    natal_rules,
    period_context,
    xuankong_natal,
)
from fatebridge.services.fengshui import assess, calculate_xuankong_natal
from fatebridge.utils.errors import EphemerisSourceError
from tests.fixtures.fengshui import payload

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/xuankong-reference.json").read_text()
)


def request(period=7, angle=0, uncertainty=0):
    return XuankongRequest.model_validate(
        {
            "house": {
                "object_id": "home",
                "facing_degrees": angle,
                "north_reference": "magnetic",
                "bearing_uncertainty_degrees": uncertainty,
            },
            "period": {
                "basis": "expert_confirmed",
                "period_number": period,
                "evidence": "已核实宅运",
            },
        }
    )


def numbers(chart):
    return {
        d: [p["period_star_number"], p["mountain_star_number"], p["facing_star_number"]]
        for d, p in chart["palaces"].items()
    }


@pytest.mark.parametrize("case", REFERENCE["published"], ids=lambda c: c["label"])
def test_published_lower_and_replacement_full_nine_palaces(case):
    chart = xuankong_natal(request(case["period"], case["facing_degrees"]))["chart"]
    assert chart["chart_mode"] == case["chart_mode"]
    assert numbers(chart) == case["palaces"]


def test_pinned_external_all_216_with_explicit_five_yellow_differences():
    assert REFERENCE["external"]["commit"] == "2eacd85b9878452469c6669e7fff05d2c6226c97"
    nonfive = matched = differences = 0
    for case in REFERENCE["external"]["cases"]:
        chart = xuankong_natal(request(case["period"], case["facing_degrees"]))["chart"]
        actual = numbers(chart)
        if 5 not in case["palaces"]["C"][1:]:
            assert actual == case["palaces"]
            nonfive += 1
        if actual == case["palaces"]:
            matched += 1
        else:
            differences += 1
            assert case["palaces"]["C"][1] == 5
            assert (
                chart["trace"]["mountain"]["five_yellow_policy"]
                == "borrow_period_same_yuan_keep_five"
            )
            assert all(actual[d][::2] == case["palaces"][d][::2] for d in actual)
    assert (nonfive, matched, differences) == (168, 192, 24)


@pytest.mark.parametrize("case", REFERENCE["five_yellow_oracle"]["cases"])
def test_all_48_five_yellow_charts_against_literal_source_polarity(case):
    chart = xuankong_natal(request(case["period"], case["facing_degrees"]))["chart"]
    side = case["side"]
    trace = chart["trace"][side]
    assert trace["seed_star_number"] == trace["center_star_number"] == 5
    assert trace["yuan"] == case["yuan"]
    assert trace["mapped_mountain"] == case["mapped_mountain"]
    assert trace["polarity"] == case["expected_polarity"]
    assert list(chart[side + "_chart"].values()) == case["five_flight_numbers"]
    assert not trace["replacement_applied"]
    external = next(
        c
        for c in REFERENCE["external"]["cases"]
        if (c["period"], c["facing_mountain"])
        == (case["period"], case["facing_mountain"])
    )
    column = 1 if side == "mountain" else 2
    literal = REFERENCE["five_yellow_oracle"][
        "reverse" if case["expected_polarity"] == "yang" else "forward"
    ]
    expected_external = literal if side == "mountain" else case["five_flight_numbers"]
    path = REFERENCE["five_yellow_oracle"]["flight_path"]
    assert [external["palaces"][d][column] for d in path] == expected_external


@pytest.mark.parametrize("i", range(24))
@pytest.mark.parametrize("offset", [-7.5, -4.5, 4.5, 7.5])
def test_nearest_representable_bearings_do_not_expand_dividing_lines(i, offset):
    boundary = (15 * i + offset) % 360
    before, after = math.nextafter(boundary, -math.inf), math.nextafter(
        boundary, math.inf
    )
    left = _selectors(before, 0)
    right = _selectors(after, 0)
    assert len(left) == len(right) == 1
    both = {s[:2] for s in _selectors(boundary, 0)}
    assert both == {left[0][:2], right[0][:2]}
    assert {s[:2] for s in _selectors(boundary - 0.5, 0.5)} == both
    assert {s[:2] for s in _selectors(boundary + 0.5, 0.5)} == both


@pytest.mark.parametrize("i", range(8))
def test_confirmed_sitting_trigram_constrains_cross_palace_candidates(i):
    boundary = 22.5 + 45 * i
    before = math.nextafter(boundary, -math.inf)
    after = math.nextafter(boundary, math.inf)
    assert (
        bearing_context(before, "magnetic")["direction"]
        != bearing_context(after, "magnetic")["direction"]
    )
    for angle in (before, boundary, after):
        req = request(angle=angle, uncertainty=1)
        trigram = sitting_from_facing(angle, "magnetic")["trigram"]
        data = req.model_dump()
        data["house"]["sitting_trigram"] = trigram
        result = xuankong_natal(XuankongRequest.model_validate(data))
        assert result["status"] == "complete"
        assert (
            result["chart"]["sitting"]["direction"]
            == sitting_from_facing(angle, "magnetic")["direction"]
        )


@pytest.mark.parametrize("failure", ["unavailable", "per_term_failure"])
def test_changeover_event_rejects_an_unavailable_native_crossing(monkeypatch, failure):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    almanac.get_solar_terms_for_year.cache_clear()
    if failure == "unavailable":
        monkeypatch.setattr(almanac, "swe", None)
    else:
        monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *a: None)
    try:
        inputs = payload("xuankong_natal")
        inputs["period"] = {
            "basis": "first_occupancy",
            "event_at": "2024-02-04T16:20:00+08:00",
            "evidence": "confirmed event time; selected provider unavailable",
        }
        with pytest.raises(EphemerisSourceError, match="no linear approximation"):
            calculate_xuankong_natal(**inputs)
        inputs["period"].pop("event_at")
        inputs["period"]["effective_event_year"] = 2024
        with pytest.raises(EphemerisSourceError, match="no linear approximation"):
            calculate_xuankong_natal(**inputs)
    finally:
        almanac.get_solar_terms_for_year.cache_clear()


@pytest.mark.parametrize("period", range(1, 10))
def test_every_mountain_lower_and_both_compatibility_sides(period):
    for mountain in natal_rules()["mountains"]:
        for offset in (-6, 0, 6):
            result = xuankong_natal(
                request(period, (mountain["center_degrees"] + offset) % 360)
            )
            assert result["status"] == "complete"
            c = result["chart"]
            assert c["facing"]["name"] == mountain["name"]
            assert (
                c["sitting"]["center_degrees"] - c["facing"]["center_degrees"]
            ) % 360 == 180
            for key in ("period_chart", "mountain_chart", "facing_chart"):
                assert sorted(c[key].values()) == list(range(1, 10))
            if period == 5:
                assert c["trace"]["mountain"]["seed_star_number"] != 5
                assert c["trace"]["facing"]["seed_star_number"] != 5
            assert all("annual_star_number" not in p for p in c["palaces"].values())


@pytest.mark.parametrize(
    "year,number",
    [
        (1863, 9),
        (1864, 1),
        (1884, 2),
        (1924, 4),
        (1944, 5),
        (1984, 7),
        (2004, 8),
        (2024, 9),
        (2044, 1),
    ],
)
def test_house_event_periods_not_query_periods(year, number):
    p = period_context(
        HousePeriod(
            basis="construction_completion",
            effective_event_year=year,
            evidence="确认立春后的有效年",
        )
    )
    assert p["number"] == number
    assert p["effective_event_year"] == year
    assert p["end_year"] - p["start_year"] == 19
    assert p["interval_scope"] == "historical_event_period_window_not_natal_expiry"


@pytest.mark.parametrize("model", ["native", "analytic", "de440"])
def test_house_event_datetime_lichun_and_timezone_equivalence(
    monkeypatch, tmp_path, model
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", model)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    boundary = lichun(2024, "Asia/Shanghai")

    def resolve(moment):
        return period_context(
            HousePeriod(
                basis="first_occupancy",
                event_at=moment,
                evidence="按已确认的首次入伙事件定运",
            )
        )

    # All three selected software models retain a five-second operational
    # candidate guard. It is separate from the unchanged one-second TT gate.
    for seconds in (-5, -1, 0, 1, 5):
        result = resolve(boundary + timedelta(seconds=seconds))
        assert result["number"] is None
        assert result["candidate_period_numbers"] == [8, 9]
    assert resolve(boundary - timedelta(seconds=6))["number"] == 8
    assert resolve(boundary + timedelta(seconds=6))["number"] == 9
    assert resolve(boundary.astimezone(lichun(2024, "UTC").tzinfo)) == resolve(boundary)


def test_changeover_date_matches_independent_published_minute():
    # An independent astronomy notice, not this engine's own boundary value.
    # It certifies the minute only. The model tests above check candidate
    # preservation against the computed instant, not independent accuracy.
    reference = REFERENCE["house_period_calendar_reference"]
    assert (
        lichun(reference["year"], "Asia/Shanghai").isoformat(timespec="minutes")
        == reference["lichun_hkt_minute"]
    )


@pytest.mark.parametrize(
    "angle,expected",
    [
        (354, "replacement"),
        (6, "lower"),
        (9, "lower"),
        (21, "replacement"),
        (39, "replacement"),
        (51, "lower"),
        (54, "lower"),
        (66, "replacement"),
    ],
)
def test_zhongzhou_same_polarity_exception_and_cross_palace(angle, expected):
    assert xuankong_natal(request(angle=angle))["chart"]["chart_mode"] == expected


@pytest.mark.parametrize("angle", [4.5, 355.5, 7.5, 22.5, 337.5, 352.5])
def test_exact_dividing_lines_return_two_candidates_when_chart_choice_differs(angle):
    result = xuankong_natal(request(angle=angle))
    # +4.5 faces 子兼癸: same-polarity exception means both limits are lower.
    if angle == 4.5:
        assert result["status"] == "complete"
    else:
        assert result["status"] == "partial"
        assert result["chart"] is None
        assert len(result["candidates"]) == 2
        assert result["missing_inputs"] == ["xuankong_natal.unambiguous_bearing"]


def test_uncertainty_partitions_entire_interval_and_wraps_north():
    # Endpoints 352.5 and 7.5 are not sufficient to observe the central 下卦 cell.
    result = xuankong_natal(request(angle=0, uncertainty=7.5))
    selections = {(c["facing"]["name"], c["chart_mode"]) for c in result["candidates"]}
    assert selections == {
        ("壬", "replacement"),
        ("子", "replacement"),
        ("子", "lower"),
        ("癸", "lower"),
    }
    assert result["status"] == "partial"
    assert xuankong_natal(request(angle=360)) == xuankong_natal(request(angle=0))


def test_replacement_keeps_original_mapped_polarity_and_five():
    chart = xuankong_natal(request(7, 129))["chart"]
    t = chart["trace"]["mountain"]
    assert (
        t["seed_star_number"],
        t["mapped_mountain"],
        t["polarity"],
        t["center_star_number"],
    ) == (8, "艮", "yang", 7)
    # Using replacement 7's heavenly 酉 polarity would incorrectly reverse it.
    assert chart["mountain_chart"]["NW"] == 8
    five = xuankong_natal(request(7, 264))["chart"]["trace"]["mountain"]
    assert (
        five["seed_star_number"],
        five["mapped_mountain"],
        five["center_star_number"],
    ) == (5, "酉", 5)
    assert not five["replacement_applied"]


def test_partial_does_not_guess_from_sitting_trigram_or_current_year():
    r = calculate_xuankong_natal(house={"sitting_trigram": "坎"})
    assert r["status"] == "partial"
    assert r["layers"]["xuankong_natal"]["chart"] is None
    assert len(r["coverage"]["missing_inputs"]) == 2


def test_natal_and_annual_are_independent_aggregate_scopes_and_explicit_opt_in():
    natal = payload("xuankong_natal")
    args = {
        "methods": ["annual_stars", "xuankong_natal"],
        "house": natal.pop("house"),
        "xuankong": natal,
    }
    a = assess(**args, effective_year=2026)
    b = assess(**args, effective_year=2027)
    assert a["layers"]["xuankong_natal"] == b["layers"]["xuankong_natal"]
    assert a["layers"]["annual_stars"] != b["layers"]["annual_stars"]
    assert a["layers"]["xuankong_natal"]["period_context"]["number"] == 8
    assert a["layers"]["annual_stars"]["current_period"]["number"] == 9
    assert (
        "xuankong_natal"
        not in assess(methods=["annual_stars"], effective_year=2026)["layers"]
    )
    assert "xuankong_natal" not in a["coverage"]["unavailable_layers"]
    assert "玄空宅盘" in a["snapshot_text"] and "年度飞星" in a["snapshot_text"]
    FengshuiOutput.model_validate(a)


@pytest.mark.parametrize(
    "patch",
    [
        {"ruleset_id": "shen_unverified_v1"},
        {
            "period": {
                "basis": "expert_confirmed",
                "period_number": 0,
                "evidence": "盘例",
            }
        },
        {
            "period": {
                "basis": "construction_completion",
                "event_at": "2024-02-01T00:00:00",
                "evidence": "盘例",
            }
        },
        {
            "period": {
                "basis": "construction_completion",
                "period_number": 8,
                "effective_event_year": 2004,
                "evidence": "盘例",
            }
        },
        {
            "period": {
                "basis": "construction_completion",
                "effective_event_year": 2004,
                "evidence": "  ",
            }
        },
        {
            "period": {
                "basis": "confirmed_major_renovation",
                "effective_event_year": 2024,
                "evidence": "油漆",
            }
        },
        {
            "period": {
                "basis": "confirmed_major_renovation",
                "effective_event_year": 2024,
                "evidence": "油漆",
                "qualifies_for_period_reset": False,
            }
        },
        {"house": {"facing_degrees": 0, "north_reference": "true"}},
        {
            "house": {
                "facing_degrees": 0,
                "north_reference": "magnetic",
                "bearing_uncertainty_degrees": 8,
            }
        },
        {"annual_year": 2026},
    ],
)
def test_invalid_natal_rules_and_evidence(patch):
    with pytest.raises(ValidationError):
        XuankongRequest.model_validate({**payload("xuankong_natal"), **patch})


def test_confirmed_renovation_evidence_is_returned_not_automatically_inferred():
    inputs = payload("xuankong_natal")
    inputs["period"] = {
        "basis": "confirmed_major_renovation",
        "period_number": 9,
        "evidence": "专业人员确认屋顶及主纳气口重建符合本次换运条件",
        "qualifies_for_period_reset": True,
    }
    assert (
        calculate_xuankong_natal(**inputs)["layers"]["xuankong_natal"][
            "period_context"
        ]["evidence"]
        == inputs["period"]["evidence"]
    )


def test_aggregate_rejects_unselected_or_inconsistent_nested_house():
    auto = assess(xuankong=payload("xuankong_natal"))
    expected = calculate_xuankong_natal(**payload("xuankong_natal"))
    assert (
        auto["layers"]["xuankong_natal"]["chart"]
        == expected["layers"]["xuankong_natal"]["chart"]
    )
    with pytest.raises(ValidationError):
        assess(
            methods=["xuankong_natal"],
            house={"facing_degrees": 180, "north_reference": "magnetic"},
            xuankong=payload("xuankong_natal"),
        )


def test_rules_version_sources_and_data_copy_are_preserved():
    r = calculate_xuankong_natal(**payload("xuankong_natal"))
    rules = r["rulesets"][0]
    assert (rules["ruleset_id"], rules["version"]) == ("xuankong_zhongzhou_v1", "1.4.0")
    assert {"X1", "X2", "X3", "X4", "X5", "X8", "X9"} <= set(rules["source_ids"])
    assert len(natal_rules()["replacement_stars"]) == 13
    edited = deepcopy(r)
    edited["layers"]["xuankong_natal"]["mountain_registry"][0]["name"] = "bad"
    assert natal_rules()["mountains"][0]["name"] == "子"
