"""Source-derived conditions retain literal overlaps and real term boundaries."""

import hashlib
import json
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from fatebridge.core.almanac import get_solar_terms_for_year, is_calculated_solar_term
from fatebridge.core.heluo import calculate, judge, solar_term
from fatebridge.core.heluo_seasonal import (
    SOURCE_SHA256,
    numerical_conditions,
    seasonal_number_evidence,
    seasonal_snapshot,
)
from fatebridge.core.output_numerology import HeluoSeasonalNumbers
from fatebridge.services.divination import calculate_heluo_analysis
from tests.support.ephemeris_context import moshier_ephemeris as golden_ephemeris

ROOT = Path(__file__).parents[1] / "fixtures/numerology_nlc_v1"
REF = json.loads((ROOT / "seasonal-reference.json").read_text())


def test_eleven_source_pages_and_rule_derivation_are_preserved():
    manifest = json.loads((ROOT / "seasonal-manifest.json").read_text())
    assert manifest["pdf_sha256"] == REF["source_pdf_sha256"] == SOURCE_SHA256
    assert [r["pdf_page"] for r in manifest["images"]] == list(range(64, 75))
    for row in manifest["images"]:
        data = (ROOT / row["file"]).read_bytes()
        assert len(data) == row["bytes"]
        assert hashlib.sha256(data).hexdigest() == row["sha256"]
    assert REF["new_classical_worked_horoscopes"] == 0
    assert "hand-derived" in REF["annotation_method"]


@pytest.mark.parametrize("case", REF["pattern_cases"])
def test_all_literal_number_patterns_against_hand_derived_probes(case):
    rows = numerical_conditions(case["tian"], case["di"])
    assert len(rows) == len(REF["formulas"]) == 11
    assert [r["rule_id"] for r in rows if r["matched"]] == case["ids"]
    assert [r["source_pdf_page"] for r in rows] == [r["page"] for r in REF["formulas"]]


@pytest.mark.parametrize("case", REF["season_cases"])
def test_original_six_windows_keep_their_gaps_and_overlaps(case):
    birth = datetime.fromisoformat(case["at"])
    result = seasonal_number_evidence(case["tian"], case["di"], birth)
    windows = result["seasonal_windows"]
    assert [w["rule_id"] for w in windows] == [w["id"] for w in REF["windows"]]
    assert [(w["start_term"], w["end_term"]) for w in windows] == [
        (w["start"], w["end"]) for w in REF["windows"]
    ]
    active = {w["rule_id"]: w["numeric_band_match"] for w in windows if w["active"]}
    assert active == case["active"]
    assert not result["complete_assessment"]


@pytest.mark.parametrize("model_context", ["runtime", "native_moshier"])
def test_independent_hko_minutes_bracket_every_start_and_end_in_three_years(
    model_context,
):
    # Retain the external minutes and transition probes. A provider's name is
    # provenance, not the accuracy oracle; match it to the actual solved term.
    context = golden_ephemeris() if model_context == "native_moshier" else nullcontext()
    with context:
        reference = json.loads(
            (ROOT.parent / "calendar_hko_v1/reference.json").read_text()
        )
        observed = set()
        term_cache = {}

        def term(year, name):
            if year not in term_cache:
                term_cache[year] = {
                    t.name: t for t in get_solar_terms_for_year(year, "+00:00")
                }
            return term_cache[year][name]

        for rule in REF["windows"]:
            for boundary, starting in ((rule["start"], True), (rule["end"], False)):
                for case in reference["cases"]:
                    if case["term"] != boundary:
                        continue
                    moment = datetime.fromisoformat(case["at"])
                    solved = term(case["year"], boundary)
                    assert is_calculated_solar_term(solved)
                    assert (
                        abs((solved.moment - moment).total_seconds())
                        <= reference["tolerance_seconds"]
                    )
                    values = []
                    for delta in (-2, 2):
                        result = seasonal_number_evidence(
                            31, 34, moment + timedelta(minutes=delta)
                        )
                        window = next(
                            w
                            for w in result["seasonal_windows"]
                            if w["rule_id"] == rule["id"]
                        )
                        values.append(window["active"])
                        for edge in ("start", "end"):
                            at = datetime.fromisoformat(window[edge + "_at"])
                            actual = term(at.year, window[edge + "_term"])
                            assert is_calculated_solar_term(actual)
                            assert at == actual.moment
                            assert (
                                window[edge + "_provider"] == actual.resolution_provider
                            )
                            if model_context == "native_moshier":
                                assert actual.resolution_provider == "swisseph"
                    assert values == ([False, True] if starting else [True, False])
                    observed.add((rule["id"], boundary, case["year"]))
        assert len(observed) == 36  # Reused external term brackets, not new horoscopes.


def test_boundary_is_inclusive_on_start_and_exclusive_on_end():
    at = datetime.fromisoformat("2026-02-10T12:00:00+08:00")
    windows = seasonal_number_evidence(31, 34, at)["seasonal_windows"]
    for row in windows:
        for boundary, active in (("start_at", True), ("end_at", False)):
            result = seasonal_number_evidence(
                31, 34, datetime.fromisoformat(row[boundary])
            )
            selected = next(
                w for w in result["seasonal_windows"] if w["rule_id"] == row["rule_id"]
            )
            assert selected["active"] is active


def test_physical_instant_is_identical_across_timezones_and_dst():
    # This interval crosses New York's 2026 autumn clock change.
    at = datetime.fromisoformat("2026-11-01T06:30:00Z")
    reference = seasonal_number_evidence(31, 52, at)
    for zone in ("America/New_York", "Asia/Shanghai"):
        assert (
            seasonal_number_evidence(31, 52, at.astimezone(ZoneInfo(zone))) == reference
        )


def test_surplus_parity_and_literal_overlaps_are_not_rewritten_as_exclusive():
    a = seasonal_number_evidence(30, 30, None)
    assert a["matched_pattern_ids"] == [
        "lone_yang_unpaired",
        "lone_yang_self_pair",
        "strong_subdues_weak",
    ]
    b = seasonal_number_evidence(25, 46, None)
    assert b["matched_pattern_ids"] == ["lone_yin_back_yang", "lone_yin_toward_yang"]
    # 46 is not a multiple of ten; p71 literally states a range, not that filter.
    assert "孤阴背阳、孤阴向阳" in seasonal_snapshot(b)
    assert "尚未裁定综合得中或葉否" in seasonal_snapshot(b)


def test_exact_reference_is_not_a_completed_seasonal_middle_assessment():
    at = datetime.fromisoformat("2026-02-10T12:00:00+08:00")
    result = seasonal_number_evidence(25, 30, at)
    assert result["numbers"]["tian"]["comparison"] == "正数"
    assert result["numbers"]["di"]["comparison"] == "正数"
    middle = next(
        w for w in result["seasonal_windows"] if w["rule_id"] == "yang_middle"
    )
    assert middle["active"] and middle["numeric_band_match"] is None
    assert "数值条件未量化" in seasonal_snapshot(result)


def test_strong_number_is_assessed_separately_from_its_seasonal_window():
    a = seasonal_number_evidence(42, 52, datetime(2026, 1, 15, tzinfo=timezone.utc))
    b = seasonal_number_evidence(42, 52, datetime(2026, 4, 15, tzinfo=timezone.utc))
    assert a["numbers"] == b["numbers"]
    assert a["numbers"]["tian"]["extreme_band"] == "太过"
    assert a["numbers"]["di"]["extreme_band"] == "太过"
    a_high = next(w for w in a["seasonal_windows"] if w["rule_id"] == "yang_high")
    b_high = next(w for w in b["seasonal_windows"] if w["rule_id"] == "yang_high")
    assert a_high["numeric_band_match"] and not a_high["active"]
    assert b_high["numeric_band_match"] and b_high["active"]


def test_extremely_weak_ranges_and_high_thresholds_preserve_their_source_limits():
    for tian, di, t_expected, d_expected in [
        (4, 8, "至弱", "至弱"),
        (8, 12, "至弱", "至弱"),
        (9, 14, None, None),
        (39, 48, None, None),
        (40, 50, "太过", "太过"),
        (60, 62, "太过", "太过"),
        (62, 64, None, "太过"),
    ]:
        numbers = seasonal_number_evidence(tian, di, None)["numbers"]
        assert numbers["tian"]["extreme_band"] == t_expected
        assert numbers["di"]["extreme_band"] == d_expected
    beyond = seasonal_number_evidence(
        62, 30, datetime(2026, 4, 15, tzinfo=timezone.utc)
    )
    assert (
        beyond["numbers"]["tian"]["extreme_band_status"] == "outside_cited_high_range"
    )
    window = next(w for w in beyond["seasonal_windows"] if w["rule_id"] == "yang_high")
    assert window["active"] and window["numeric_band_match"] is None
    assert "超出所核数段，不外推" in seasonal_snapshot(beyond)


def test_missing_birth_instant_has_no_seasonal_or_current_date_fallback():
    evidence = seasonal_number_evidence(31, 34, None)
    assert evidence["seasonal_status"] == "not_evaluated_missing_birth_instant"
    assert evidence["birth_instant_utc"] is None and evidence["seasonal_windows"] == []
    pillars = {"year": "甲子", "month": "丁卯", "day": "庚申", "hour": "庚辰"}
    chart = calculate(
        four_pillars=pillars,
        gender="男",
        hour_zhi="辰",
        birth_year=1924,
        month_zhi="卯",
    )
    # A date-only solar helper is explicitly a midnight approximation.
    approximation = solar_term(2026, 2, 10, "+08:00")
    assert (
        judge(chart, pillars, "卯", approximation)["seasonal_numbers"][
            "seasonal_windows"
        ]
        == []
    )
    chart.update(tian=25, di=30)
    exact = judge(chart, pillars, "卯")
    assert exact["erShu"]["tianState"] == exact["erShu"]["diState"] == "正数"
    chart.update(tian=42, di=52)
    high = judge(chart, pillars, "卯")
    assert high["erShu"]["tianState"] == high["erShu"]["diState"] == "有余"
    assert high["seasonal_numbers"]["numbers"]["tian"]["extreme_band"] == "太过"


def test_published_evidence_and_snapshot_use_same_run_facts_and_birth_instant():
    args = dict(date="2026-02-10", time="12:00:00", zone="Asia/Shanghai", gender="女")
    a = calculate_heluo_analysis(**args, lon="75", use_true_solar_time=False)
    b = calculate_heluo_analysis(**args, lon="75", use_true_solar_time=True)
    evidence = a["judge"]["seasonal_numbers"]
    assert (
        evidence["birth_instant_utc"]
        == b["judge"]["seasonal_numbers"]["birth_instant_utc"]
    )
    assert (
        evidence["seasonal_windows"]
        == b["judge"]["seasonal_numbers"]["seasonal_windows"]
    )
    trace = next(
        r
        for r in a["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == evidence["ruleset_id"]
    )
    assert trace["facts"] == evidence
    assert seasonal_snapshot(evidence) in a["snapshot_text"]


@pytest.mark.parametrize(
    "values", [(True, 30), (25, False), (0, 30), (25, -1), (25.0, 30)]
)
def test_invalid_or_coerced_counts_cannot_enter_the_rules(values):
    with pytest.raises(ValueError):
        seasonal_number_evidence(*values, None)


def test_naive_birth_is_not_silently_assigned_a_timezone():
    with pytest.raises(ValueError):
        seasonal_number_evidence(31, 34, datetime(2026, 2, 10))


@pytest.mark.parametrize(
    "payload",
    [
        {"numbers": {"tian": {"value": "25"}}},
        {"numerical_conditions": [{"matched": "true"}]},
        {"seasonal_windows": [{"active": 1}]},
        {"complete_assessment": True},
    ],
)
def test_corrupt_or_overclaimed_facts_fail_the_strict_contract(payload):
    with pytest.raises(ValidationError):
        HeluoSeasonalNumbers.model_validate(payload)


def test_hko_check_still_rejects_a_two_minute_error_with_valid_provider(monkeypatch):
    from dataclasses import replace

    original = get_solar_terms_for_year

    def shifted(year, zone):
        return [
            replace(t, moment=t.moment + timedelta(minutes=2))
            for t in original(year, zone)
        ]

    monkeypatch.setitem(globals(), "get_solar_terms_for_year", shifted)
    with pytest.raises(AssertionError):
        test_independent_hko_minutes_bracket_every_start_and_end_in_three_years(
            "runtime"
        )
