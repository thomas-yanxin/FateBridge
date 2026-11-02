"""Independent original-text, official calendar and explicit clock adapters."""

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.local_techniques.sanshi import _build_taiyi_with_options
from fatebridge.core.metaphysics import taiyi_periods as periods
from fatebridge.core.metaphysics.taiyi_year import cyclic_core, structural_patterns
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import (
    _build_analysis_seed,
    calculate_taiyi_analysis,
)
from scripts.audit_taiyi_classical import DEPTH_CORPUS, audit_yin, verify_depth_sources

CALENDAR = json.loads((DEPTH_CORPUS / "calendar-cases.json").read_text())
WORKED = json.loads((DEPTH_CORPUS / "worked-cases.json").read_text())
YIN = json.loads((DEPTH_CORPUS / "yin-cases.json").read_text())
DISPUTED = {11, 15, 25, 26, 27, 43, 44, 46, 70}


def seed_at(moment: datetime, *, zone="Asia/Shanghai", solar=False, longitude=None):
    return _build_analysis_seed(
        analysis_year=moment.year,
        analysis_month=moment.month,
        analysis_day=moment.day,
        analysis_hour=moment.hour,
        analysis_minute=moment.minute,
        analysis_second=moment.second,
        analysis_timezone=zone,
        use_true_solar_time=solar,
        analysis_longitude=longitude,
    )


def board_at(moment: datetime, mode: str, **kwargs):
    return periods.build_period_board(seed_at(moment, **kwargs), "未知", mode)


@pytest.mark.parametrize("case", YIN, ids=lambda c: c["id"])
def test_full_yin_table_includes_disagreements(case):
    actual = cyclic_core(case["accumulation"], yin=True)
    checks = [actual[k] == v for k, v in case["expected"].items()]
    # A green test means the audit preserved the known failure; it does not
    # relabel that row a classical pass, xfail it, or drop it from the denominator.
    assert all(checks) is (case["accumulation"] not in DISPUTED)


def test_yin_audit_keeps_all_failed_fields_and_facsimile_readings():
    report = audit_yin()
    assert (report["total_cases"], report["matching_cases"]) == (72, 63)
    assert (report["checked_fields"], report["matching_fields"]) == (144, 135)
    assert {x["ju"] for x in report["disagreements"]} == DISPUTED
    assert report["classical_acceptance_passed"] is False
    collation = json.loads((DEPTH_CORPUS / "collation.json").read_text())
    readings = {
        (x["ju"], x["field"]): x["facsimile_reading"]
        for x in collation["yin_table_disputes"]
    }
    assert {
        (x["ju"], x["field"]): x["expected_transcription"]
        for x in report["disagreements"]
    } == readings


def test_alternate_manuscript_constants_are_kept_separate_by_edition():
    verify_depth_sources()
    variants = json.loads((DEPTH_CORPUS / "calendar-variants.json").read_text())
    by_name = {v["name"]: v for v in variants["variants"]}
    assert (
        by_name["月法"]["ming_facsimile"] == 29 * 49 + by_name["朔余"]["ming_facsimile"]
    )
    assert (
        by_name["月法"]["siku_transcription"]
        != 29 * 49 + by_name["朔余"]["siku_transcription"]
    )
    assert by_name["章月"]["ming_facsimile"] == 8126
    assert by_name["章月"]["siku_transcription"] == 8726


@pytest.mark.parametrize(
    "option",
    [
        {"calculation_mode": []},
        {"calculation_mode": {}},
        {"calculation_mode": None},
        {"calculation_mode": "week"},
        {"rotation": []},
    ],
)
def test_malformed_sanshi_options_are_parameter_errors_not_server_exceptions(option):
    with pytest.raises(ValueError):
        _build_taiyi_with_options(seed_at(datetime(2026, 6, 21, 17)), option)


@pytest.mark.parametrize("attempt", ["source", "drop_case", "drop_field"])
def test_depth_oracle_tampering_fails_even_if_manifest_hash_is_updated(
    tmp_path, attempt
):
    corpus = tmp_path / "taiyi_jinjing_v2"
    shutil.copytree(DEPTH_CORPUS, corpus)
    shutil.copytree(
        DEPTH_CORPUS.parent / "taiyi_jinjing_v1", tmp_path / "taiyi_jinjing_v1"
    )
    if attempt == "source":
        (corpus / "naoj-2026.html").write_text("tampered")
        with pytest.raises(ValueError, match="指纹"):
            verify_depth_sources(corpus)
        return
    path = corpus / "yin-cases.json"
    cases = json.loads(path.read_text())
    if attempt == "drop_case":
        cases.pop(10)
    else:
        del cases[10]["expected"]["guest_count"]
    path.write_text(json.dumps(cases))
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["source_files"]:
        if item["file"] == path.name:
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="72|每局必须"):
        audit_yin(corpus)


@pytest.mark.parametrize("case", WORKED, ids=lambda c: c["id"])
def test_six_ji_initial_configurations_from_volume_one(case):
    if "modern_example_date" in case:
        board = board_at(
            datetime.fromisoformat(case["modern_example_date"] + "T12:00:00"), "month"
        )
        core = board["core_board"]
        # These dates were authored engineering representatives, not dated
        # passages in the source. Keep every old date and expose its changed
        # phase; compare the undated source configuration at its given cycle.
        assert (core["accumulation"] - 1) % 360 + 1 == (
            case["cycle_index"] + 12 - 1
        ) % 360 + 1
        actual = cyclic_core(case["cycle_index"], yin=False)
    else:
        actual = cyclic_core(case["cycle_index"], yin=True)
    for field, expected in case["expected"].items():
        if field == "heshen":
            # The undated source specifies 庚申 day: 巳合申. A cyclic core
            # has no day, and the source gives no year to reconstruct one.
            assert case["id"] == "volume-one-taiyi-dangshi-yin27"
            continue
        assert actual[field] == expected


def test_dangshi_heshen_uses_explicit_given_day_not_the_hour(monkeypatch):
    seed = seed_at(datetime(2026, 6, 21, 17))
    seed = replace(seed, pillars={**seed.pillars, "day": "庚申", "hour": "戊寅"})
    frame = periods.period_frame(seed, "hour")
    monkeypatch.setattr(
        periods,
        "period_frame",
        lambda *args: {**frame, "accumulation": 27, "yin": True, "ruler_branch": "寅"},
    )
    board = periods.build_period_board(seed, "未知", "hour")
    assert board["core_board"]["heshen"] == "巳"
    assert board["calendar_rules"]["heshen_branch_basis"] == "day_pillar_branch"


@pytest.mark.parametrize(
    "case",
    CALENDAR["cases"] + CALENDAR["hko_solstices"],
    ids=lambda c: c["term"] + c["at"],
)
@pytest.mark.parametrize(
    "source,provider", [("native", "swisseph"), ("de440", "jpl_de440")]
)
def test_astronomical_terms_against_two_official_observatories(
    case, source, provider, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", source)
    terms = {t.name: t for t in get_solar_terms_for_year(2026, "UTC")}
    term = terms[case["term"]]
    assert term.resolution_provider == provider
    assert (
        abs((term.moment - datetime.fromisoformat(case["at"])).total_seconds())
        <= CALENDAR["tolerance_seconds"]
    )


@pytest.mark.parametrize(
    "case",
    [c for c in CALENDAR["cases"] if c["term"] in periods.JIE_ORDER],
    ids=lambda c: c["term"],
)
def test_month_changes_at_each_jie_not_midnight_or_lunar_month(case):
    # Two minutes away is safely outside the published-minute precision band.
    published = datetime.fromisoformat(case["at"]).astimezone(timezone.utc)
    before = periods.period_frame(
        seed_at((published - timedelta(minutes=2)).replace(tzinfo=None), zone="UTC"),
        "month",
    )
    after = periods.period_frame(
        seed_at((published + timedelta(minutes=2)).replace(tzinfo=None), zone="UTC"),
        "month",
    )
    assert after["anchor"].name == case["term"]
    assert before["accumulation"] + 1 == after["accumulation"]
    assert after["month_offset"] == periods.JIE_ORDER.index(case["term"])


def test_lunar_leap_six_does_not_add_a_solar_month():
    # Independent HKO 2025 calendar: July25 starts leap six, no Jie that day.
    before = board_at(datetime(2025, 7, 24, 12), "month")
    after = board_at(datetime(2025, 7, 25, 12), "month")
    assert before["core_board"] == after["core_board"]
    assert after["calendar_rules"]["month_offset"] == 7  # 小暑 / 未月
    assert after["calendar_rules"]["leap_month_policy"]


@pytest.mark.parametrize(
    "moment,rotation,ju",
    [
        ("2026-06-21T16:27:00", "逆布", 1),
        ("2026-06-21T16:59:59", "逆布", 1),
        ("2026-06-21T17:00:00", "逆布", 2),
        ("2026-12-22T04:52:00", "顺布", 1),
        ("2026-12-22T05:00:00", "顺布", 2),
        ("2026-12-22T09:00:00", "顺布", 4),
    ],
)
def test_solstice_partial_interval_and_double_hour_boundaries(moment, rotation, ju):
    board = board_at(datetime.fromisoformat(moment), "hour")
    assert board["rotation"] == rotation
    assert board["core_board"]["kook_number"] == ju
    assert board["calendar_rules"]["counter"] == ju
    assert board["ruleset"]["classical_acceptance_passed"] is False
    assert "现代适配" in board["calendar_rules"]["modern_conventions"]


def test_solstice_switch_compares_instants_at_second_resolution(monkeypatch):
    # Synthetic anchor isolates the boundary operator; official tests above
    # only certify minute-scale agreement, not the solver's second accuracy.
    real = next(t for t in get_solar_terms_for_year(2026, "UTC") if t.name == "夏至")
    anchor = replace(real, moment=datetime(2026, 6, 21, 8, 24, 31, tzinfo=timezone.utc))
    previous = next(
        t for t in get_solar_terms_for_year(2025, "UTC") if t.name == "冬至"
    )
    monkeypatch.setattr(
        periods, "get_solar_terms_for_year", lambda *args: [previous, anchor]
    )
    before = periods.period_frame(seed_at(datetime(2026, 6, 21, 16, 24, 30)), "hour")
    at = periods.period_frame(seed_at(datetime(2026, 6, 21, 16, 24, 31)), "hour")
    assert before["yin"] is False
    assert at["yin"] is True and at["accumulation"] == 1


def test_23_hour_zi_boundary_is_continuous_through_midnight():
    slots = [
        periods._slot(datetime.fromisoformat(s))
        for s in [
            "2026-06-21T22:59:59.999999",
            "2026-06-21T23:00:00",
            "2026-06-22T00:59:59.999999",
            "2026-06-22T01:00:00",
        ]
    ]
    assert slots == [slots[0], slots[0] + 1, slots[0] + 1, slots[0] + 2]


@pytest.mark.parametrize("mode", ["month", "hour"])
def test_apparent_solar_counter_is_invariant_under_timezone_representation(mode):
    utc = datetime(2026, 8, 1, 12, 34, 56)
    a = board_at(utc, mode, zone="UTC", solar=True, longitude=121.47)
    b = board_at(
        utc + timedelta(hours=8),
        mode,
        zone="Asia/Shanghai",
        solar=True,
        longitude=121.47,
    )
    c = board_at(
        utc - timedelta(hours=4),
        mode,
        zone="America/New_York",
        solar=True,
        longitude=121.47,
    )
    assert (
        a["calendar_rules"]["counter"]
        == b["calendar_rules"]["counter"]
        == c["calendar_rules"]["counter"]
    )
    for k in (
        "taiyi_palace",
        "wenchang_palace",
        "rule_trace",
        "palace_marks",
        "center_marks",
    ):
        assert a[k] == b[k] == c[k]
    if mode == "hour":
        assert (
            a["calendar_rules"]["target_clock"]
            == b["calendar_rules"]["target_clock"]
            == c["calendar_rules"]["target_clock"]
        )


@pytest.mark.parametrize(
    "moment", [datetime(2026, 3, 8, 2, 30), datetime(2026, 11, 1, 1, 30)]
)
def test_ambiguous_or_nonexistent_civil_clock_is_rejected(moment):
    with pytest.raises(ValueError, match="local time"):
        seed_at(moment, zone="America/New_York")


def test_approximate_solar_term_fallback_cannot_silently_set_a_period(monkeypatch):
    real = next(t for t in get_solar_terms_for_year(2026, "UTC") if t.name == "夏至")
    monkeypatch.setattr(
        periods,
        "get_solar_terms_for_year",
        lambda *args: [replace(real, resolution_provider="linear_1900_fallback")],
    )
    with pytest.raises(ValueError, match="线性近似"):
        periods.period_frame(seed_at(datetime(2026, 7, 1, 12)), "hour")


@pytest.mark.parametrize("mode", ["month", "hour"])
def test_public_clock_mode_is_preserved_in_sanshi_and_standalone(mode):
    standalone = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=6,
        analysis_day=21,
        analysis_hour=17,
        analysis_minute=0,
        analysis_second=2,
        calculation_mode=mode,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    joined = calculate_sanshiunited_analysis(
        date="2026-06-21",
        time="17:00:02",
        zone="Asia/Shanghai",
        use_true_solar_time=False,
        taiyi_options={"calculation_mode": mode},
    )
    assert standalone["taiyi"] == joined["taiyi"]
    assert joined["synthesis"]["time_scopes"]["taiyi"] == (
        "solar_month" if mode == "month" else "double_hour"
    )
    assert "17:00:02" in standalone["taiyi"]["calendar_rules"]["civil_datetime"]
    core = standalone["taiyi"]["core_board"]
    assert "suijun" not in core
    assert core["ruler_label"] == ("月建" if mode == "month" else "时支")
    assert (
        core["ruler_label"] + "：" + core["ruler_branch"] in standalone["snapshot_text"]
    )
    assert not any("太歲" in p["markers"] for p in standalone["taiyi"]["palace_marks"])


def test_volume_three_yang_first_ju_captivity_and_opposition_are_individual():
    # 卷三阳局1: 主参一乾(囚)，客参九巽(格); no all-four condition.
    # 卷三掩法及图书集成阳1另明确始击坤七掩主大将，不能漏记。
    pats = structural_patterns(cyclic_core(1))
    assert {(p["name"], p["subject"]) for p in pats} == {
        ("囚", "主参将"),
        ("格", "客参将"),
        ("掩", "始击"),
    }
    yan = next(p for p in pats if p["name"] == "掩")
    assert yan["variant"] == "始击掩主大将"
    assert yan["basis"] == [
        {"field": "core_board.shiji", "value": "坤"},
        {"field": "core_board.main_general", "value": 7},
    ]


@pytest.mark.parametrize(
    "palace,variant",
    [("亥", "前击"), ("戌", "后击"), ("子", "外宫击"), ("酉", "内宫击")],
)
def test_source_spatial_predicate_each_direction_and_no_upper_eye_oppression(
    palace, variant
):
    core = {**cyclic_core(1), "shiji": palace}
    patterns = structural_patterns(core)
    assert any(p["name"] == "击" and p["variant"] == variant for p in patterns)
    assert not any(p["name"] == "迫" and p["subject"] == "始击" for p in patterns)


def test_equal_generals_in_center_are_recorded_without_directional_fabrication():
    core = {
        **cyclic_core(1),
        "main_general": 5,
        "guest_general": 5,
        "main_vice_general": 5,
        "guest_vice_general": 5,
    }
    pats = structural_patterns(core)
    assert len([p for p in pats if p["name"] == "关"]) == 4
    assert not any(
        p["name"] in {"迫", "格", "囚"} and "将" in p["subject"] for p in pats
    )
