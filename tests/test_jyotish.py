"""Indian rules: published worked examples, interval semantics and sensitivity."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import (
    DASHA_ORDER,
    GRAHAS,
    YEAR_DAYS,
    build_india,
    dignity,
    divisional_chart,
    nakshatra,
    varga_longitude,
    vimshottari,
)
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.jyotish import calculate_vimshottari
from tests.fixtures.surface_payloads import astro_payload

UTC = timezone.utc
BIRTH = datetime(2000, 4, 28, 9, 50, tzinfo=UTC)


@pytest.mark.parametrize(
    "longitude,division,sign", [(71, 9, 9), (229, 9, 8), (70, 10, 5), (229, 10, 9)]
)
def test_pvr_textbook_examples_16_and_17(longitude, division, sign):
    # Source chapter 6, examples 16/17: Mercury Gemini 11° / Jupiter Scorpio
    # 19° for D9; Mercury Gemini 10° / Jupiter Scorpio 19° for D10.
    assert int(varga_longitude(longitude, division) // 30) == sign


def test_pvr_example_50_birth_balance_and_complete_first_major():
    # Source §16.2 example 50 supplies the Moon position, not a modern
    # ephemeris fixture: Aquarius 2°23', Dhanishtha pada 3, Mars balance 2.24875y.
    result = vimshottari(BIRTH, 302 + 23 / 60, BIRTH, year_basis="savana_360")
    assert result["seed"]["name"] == "Dhanishta"
    assert result["seed"]["pada"] == 3
    assert result["seed"]["lord"] == "Mars"
    assert result["birth_balance"]["remaining_years"] == pytest.approx(2.24875)
    end = datetime.fromisoformat(result["birth_balance"]["major_end"])
    assert end - BIRTH == timedelta(days=809, hours=13, minutes=12)
    # §16.3: first AD uses the full seven-year Mars period, not its remainder.
    assert result["current_sub"]["lord"] == "Ketu"
    first = result["timeline"][0]
    assert first["antardashas"][0]["lord"] == "Mars"
    assert datetime.fromisoformat(first["antardashas"][0]["start"]) < BIRTH


@pytest.mark.parametrize("basis", YEAR_DAYS)
def test_all_major_and_subperiod_boundaries_are_contiguous_and_half_open(basis):
    result = vimshottari(BIRTH, 302 + 23 / 60, BIRTH, year_basis=basis)
    periods = result["timeline"]
    for i, major in enumerate(periods):
        start, end = map(datetime.fromisoformat, [major["start"], major["end"]])
        if i:
            assert periods[i - 1]["end"] == major["start"]
        assert major["antardashas"][0]["start"] == major["start"]
        assert major["antardashas"][-1]["end"] == major["end"]
        for j, sub in enumerate(major["antardashas"]):
            if j:
                assert major["antardashas"][j - 1]["end"] == sub["start"]
            boundary = datetime.fromisoformat(sub["start"])
            if boundary >= BIRTH:
                at = vimshottari(BIRTH, 302 + 23 / 60, boundary, year_basis=basis)
                assert at["current_major"]["lord"] == major["lord"]
                assert at["current_sub"]["lord"] == sub["lord"]
                before = vimshottari(
                    BIRTH,
                    302 + 23 / 60,
                    boundary - timedelta(microseconds=1),
                    year_basis=basis,
                )
                assert (
                    before["current_major"]["lord"],
                    before["current_sub"]["lord"],
                ) != (major["lord"], sub["lord"])
        assert (end - start).total_seconds() == pytest.approx(
            major["duration_years"] * YEAR_DAYS[basis] * 86400
        )
    cycle_end = datetime.fromisoformat(periods[-1]["end"])
    at_end = vimshottari(BIRTH, 302 + 23 / 60, cycle_end, year_basis=basis)
    assert at_end["timeline_scope"]["cycle_index"] == 1
    assert at_end["current_major"]["lord"] == "Mars"
    assert at_end["current_sub"]["lord"] == "Mars"


def test_nakshatra_and_varga_wrap_and_exact_boundaries():
    assert nakshatra(0)["lord"] == "Ketu"
    assert nakshatra(360) == nakshatra(0)
    assert nakshatra(40)["index"] == 4
    assert nakshatra(10)["pada"] == 4
    assert nakshatra(120)["index"] == 10
    for d in [1, 9, 10]:
        assert varga_longitude(360, d) == varga_longitude(0, d)
        assert 0 <= varga_longitude(359.9999999, d) < 360
    assert varga_longitude(3, 10) == 30
    assert varga_longitude(30, 10) == 270
    with pytest.raises(ValueError):
        varga_longitude(10, 60)


def test_graha_drishti_and_node_doctrine_are_independent_of_western_aspects():
    raw = {"ascendant": 0, "longitudes": {p: 0 for p in GRAHAS}}
    chart = divisional_chart(raw, 1)
    assert [h["lord"] for h in chart["houses"]] == [
        "Mars",
        "Venus",
        "Mercury",
        "Moon",
        "Sun",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Saturn",
        "Jupiter",
    ]
    for planet, houses in {
        "Mars": [4, 7, 8],
        "Jupiter": [5, 7, 9],
        "Saturn": [3, 7, 10],
        "Sun": [7],
    }.items():
        assert [
            a["target_house"]
            for a in chart["graha_aspects"]
            if a["from_planet"] == planet
        ] == houses
    assert not any(a["from_planet"] in {"Rahu", "Ketu"} for a in chart["graha_aspects"])
    assert dignity("Rahu", 10)["state"] == "not_assigned"
    assert dignity("Mercury", 5) == {
        **dignity("Mercury", 5),
        "state": "exalted",
        "own_sign": True,
    }
    assert dignity("Sun", 6)["state"] == "debilitated"


def test_india_core_contains_nine_grahas_sources_and_theme_factors():
    result = calculate_core_chart_analysis(
        chart_variant="india_chart", **astro_payload()
    )
    india = result["india"]
    assert india["status"] == "complete"
    assert set(india["charts"]) == {"D1", "D9", "D10"}
    planets = {p["id"]: p for p in india["charts"]["D1"]["planets"]}
    assert set(planets) == set(GRAHAS)
    assert (
        planets["Ketu"]["longitude"] - planets["Rahu"]["longitude"]
    ) % 360 == pytest.approx(180)
    assert india["birth_time_sensitivity"]["status"] == "not_assessed"
    for topic in ["personality", "career", "relationship"]:
        assert india["topic_evidence"][topic]["factors"]
        assert all(
            f["source_id"] in {s["id"] for s in india["rulesets"]}
            for f in india["topic_evidence"][topic]["factors"]
        )
    assert {r["rule_id"] for r in india["rule_trace"]} >= set(
        india["charts"]["D1"]["rule_ids"]
    )
    assert "western_reference_only" in result["interpretation"]["scope"]
    assert "india only" in result["interpretation"]["vedic"]["scope"]
    assert result["interpretation"]["signature"]
    assert "D9 上升" in result["snapshot_text"]
    assert "D10 上升" in result["snapshot_text"]
    assert "历史参考" in result["snapshot_text"]
    assert "vedicastrologer.org" in result["snapshot_text"]


def test_true_nodes_division_selection_and_birth_time_grid():
    birth = build_astro_birth_info(**astro_payload())
    mean = build_india(birth, divisions=[])
    true = build_india(
        birth, node_mode="true", divisions=[10], birth_time_uncertainty_minutes=5
    )
    assert set(mean["charts"]) == {"D1"}
    assert set(true["charts"]) == {"D1", "D10"}
    a = mean["charts"]["D1"]["planets"][-2]["longitude"]
    b = true["charts"]["D1"]["planets"][-2]["longitude"]
    assert a != b
    sensitivity = true["birth_time_sensitivity"]
    assert sensitivity["sample_count"] == 21
    assert sensitivity["status"] == "changes_detected"
    assert len(sensitivity["moon_samples"]) == 3


@pytest.mark.parametrize("year,month,day,hour", [(2024, 3, 10, 2), (2024, 11, 3, 1)])
def test_dst_nonexistent_and_ambiguous_birth_clocks_are_rejected(
    year, month, day, hour
):
    result = calculate_vimshottari(
        **{
            **astro_payload(),
            "birth_year": year,
            "birth_month": month,
            "birth_day": day,
            "birth_hour": hour,
            "birth_timezone": "America/New_York",
        },
        analysis_year=2026,
    )
    assert result["error_code"] == "validation_error"


def test_explicit_fixed_offset_disambiguates_birth_and_target():
    payload = {
        **astro_payload(),
        "birth_year": 2024,
        "birth_month": 11,
        "birth_day": 3,
        "birth_hour": 1,
    }
    first = calculate_vimshottari(
        **{**payload, "birth_timezone": "-04:00"}, analysis_year=2026
    )
    second = calculate_vimshottari(
        **{**payload, "birth_timezone": "-05:00"}, analysis_year=2026
    )
    assert "error" not in first and "error" not in second
    assert (
        first["vimshottari"]["seed"]["moon_longitude"]
        != second["vimshottari"]["seed"]["moon_longitude"]
    )


@pytest.mark.native_engine_fault
def test_missing_ephemeris_fails_honestly(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    result = calculate_vimshottari(**astro_payload(), analysis_year=2026)
    assert "error" in result
    assert "vimshottari" not in result


def test_solar_rebasing_cannot_hide_an_invalid_recorded_civil_clock():
    payload = {
        **astro_payload(),
        "birth_year": 2024,
        "birth_month": 3,
        "birth_day": 10,
        "birth_hour": 2,
        "birth_timezone": "America/New_York",
        "use_true_solar_time": True,
    }
    for result in [
        calculate_vimshottari(**payload, analysis_year=2026),
        calculate_core_chart_analysis(**payload, chart_variant="india_chart"),
    ]:
        assert result["error_code"] == "validation_error"


def test_native_india_uses_proleptic_gregorian_and_subsecond_instants():
    from fatebridge.core.jyotish import positions

    birth = build_astro_birth_info(
        **{**astro_payload(), "birth_year": 1500, "birth_timezone": "UTC"}
    )
    raw = positions(birth)
    assert raw["julian_day_ut"] == runtime.swe.julday(
        1500, 4, 6, 9 + 33 / 60, runtime.swe.GREG_CAL
    )
    later = positions(birth, birth.utc_datetime + timedelta(microseconds=500000))
    assert (later["julian_day_ut"] - raw["julian_day_ut"]) * 86400 == pytest.approx(
        0.5, abs=0.0001
    )


def test_legacy_explicit_tropical_override_does_not_fabricate_vargas():
    result = calculate_core_chart_analysis(
        chart_variant="india_chart", zodiacal=0, hsys=3, **astro_payload()
    )
    assert result["india"]["status"] == "configuration_not_supported"
    assert "charts" not in result["india"]


def test_parallel_native_positions_are_isolated_from_other_sidereal_mode_requests():
    birth = build_astro_birth_info(**astro_payload())
    expected = build_india(birth, divisions=[])

    def calculate(i):
        if i % 2:
            with runtime.preserve_ephemeris_path():
                runtime.swe.set_sid_mode(runtime.swe.SIDM_FAGAN_BRADLEY)
        return build_india(birth, divisions=[])["charts"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(
            charts == expected["charts"] for charts in pool.map(calculate, range(12))
        )
