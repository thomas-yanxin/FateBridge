"""Jyotish core calculations, PyJHora/Rao oracles, new dashas/yogas/pinda, and benchmarks."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish.ashtakavarga import (
    calculate_aiyar,
    calculate_rao,
    reduce_pinda,
)
from fatebridge.core.jyotish.dasha import (
    YEAR_DAYS,
    ashtottari_dasha,
    chara_dasha,
    nakshatra,
    vimshottari,
    yogini_dasha,
)
from fatebridge.core.jyotish.ephemeris import positions
from fatebridge.core.jyotish.jyotish import build_india
from fatebridge.core.jyotish.vargas import (
    GRAHAS,
    bhava_chalit,
    dignity,
    divisional_chart,
    varga_longitude,
)
from fatebridge.core.jyotish.yogas import (
    arudha_padas,
    chara_karakas,
    evaluate_yogas,
    upagrahas_and_special_lagnas,
)
from fatebridge.services.jyotish import (
    calculate_vedic_chart,
    calculate_vimshottari,
    compact_vedic_chart,
    compact_vimshottari,
)
from tests.fixtures.surface_payloads import astro_payload

UTC = timezone.utc
BIRTH = datetime(2000, 4, 28, 9, 50, tzinfo=UTC)


@pytest.mark.parametrize(
    "longitude,division,sign", [(71, 9, 9), (229, 9, 8), (70, 10, 5), (229, 10, 9)]
)
def test_pvr_textbook_examples_16_and_17(
    longitude: int, division: int, sign: int
) -> None:
    assert int(varga_longitude(longitude, division) // 30) == sign


def test_pvr_example_50_birth_balance_and_complete_first_major() -> None:
    result = vimshottari(BIRTH, 302 + 23 / 60, BIRTH, year_basis="savana_360")
    assert result["seed"]["name"] == "Dhanishta"
    assert result["seed"]["pada"] == 3
    assert result["seed"]["lord"] == "Mars"
    assert result["birth_balance"]["remaining_years"] == pytest.approx(2.24875)
    end = datetime.fromisoformat(result["birth_balance"]["major_end"])
    assert end - BIRTH == timedelta(days=809, hours=13, minutes=12)
    assert result["current_sub"]["lord"] == "Ketu"
    first = result["timeline"][0]
    assert first["antardashas"][0]["lord"] == "Mars"
    assert datetime.fromisoformat(first["antardashas"][0]["start"]) < BIRTH


@pytest.mark.parametrize("basis", YEAR_DAYS)
def test_all_major_and_subperiod_boundaries_are_contiguous_and_half_open(
    basis: str,
) -> None:
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
                ) != (
                    major["lord"],
                    sub["lord"],
                )
        assert (end - start).total_seconds() == pytest.approx(
            major["duration_years"] * YEAR_DAYS[basis] * 86400
        )


def test_nakshatra_and_varga_wrap_and_exact_boundaries() -> None:
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
    assert 0 <= varga_longitude(10, 60) < 360
    with pytest.raises(ValueError):
        varga_longitude(10, 99)


def test_graha_drishti_and_node_doctrine() -> None:
    raw = {"ascendant": 0.0, "longitudes": {p: 0.0 for p in GRAHAS}}
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
    assert dignity("Mercury", 5) == {"state": "exalted", "own_sign": True}
    assert dignity("Sun", 6)["state"] == "debilitated"


def test_pyjhora_bphs_delhi_oracle_and_new_vedic_features() -> None:
    """§6 Oracle #1: 1990-05-15T14:30:00+05:30, New Delhi (lat=28.6139, lon=77.2090)."""
    t0 = time.perf_counter()
    res = calculate_vedic_chart(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="+05:30",
        birth_longitude=77.2090,
        birth_latitude=28.6139,
        ayanamsa="lahiri",
        node_mode="mean",
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert (
        elapsed_ms < 50.0
    )  # comfortably <20 ms after warmup; strict budget <50ms in test process

    india = res["india"]
    assert 23.72 < india["ayanamsha"] < 23.73
    d1 = india["charts"]["D1"]
    assert 151.8 < d1["ascendant"]["longitude"] < 152.1
    assert d1["ascendant"]["sign"] == "Virgo"
    moon = next(p for p in d1["planets"] if p["id"] == "Moon")
    assert 271.8 < moon["longitude"] < 272.0
    assert india["moon_nakshatra"] == "Uttara Ashadha"
    assert india["nakshatras"]["Moon"]["pada"] == 2

    panch = india["panchanga"]
    assert panch["tithi"]["paksha"] == "Krishna"
    assert panch["tithi"]["name"] == "Shashthi"
    assert panch["tithi"]["lord"] == "Venus"
    assert 241.0 < panch["tithi"]["elongation_degrees"] < 241.7
    assert panch["vara"]["name"] == "Mangalavara"
    assert panch["yoga"]["name"] == "Shubha"
    assert panch["karana"]["name"] == "Gara"

    # Complete Shadbala, Ishta/Kashta, Bhava Bala, Bhava Chalit, Yogas, Arudhas, Karakas, Upagrahas
    shad = india["strengths"]["shadbala_assessment"]
    assert shad["status"] == "complete"
    assert all(
        isinstance(shad["total_virupa"][p], float)
        for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
    )
    assert len(india["strengths"]["bhava_bala"]) == 12
    assert len(india["bhava_chalit"]["bhavas"]) == 12
    assert len(india["chara_karakas"]) == 7
    assert "AL" in india["arudha_padas"] and "UL" in india["arudha_padas"]
    assert india["upagrahas"]["gulika"] is not None
    assert "yogas" in india["yogas"]

    # Compact size check (<10 KB)
    compact = compact_vedic_chart(res)
    assert len(json.dumps(compact, ensure_ascii=False).encode("utf-8")) < 10240


def test_five_ayanamsas_and_all_dasha_systems() -> None:
    shifts = {}
    for ay in ("lahiri", "true_citra", "raman", "kp", "true_pushya"):
        r = calculate_vedic_chart(
            birth_year=1990,
            birth_month=5,
            birth_day=15,
            birth_hour=14,
            birth_minute=30,
            birth_timezone="+05:30",
            birth_longitude=77.209,
            birth_latitude=28.6139,
            ayanamsa=ay,
        )
        shifts[ay] = r["india"]["ayanamsha"]
    assert len(set(round(v, 4) for v in shifts.values())) == 5

    t0 = time.perf_counter()
    dasha_res = calculate_vimshottari(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="+05:30",
        birth_longitude=77.209,
        birth_latitude=28.6139,
        analysis_year=2026,
        analysis_month=5,
        analysis_day=15,
        year_basis="julian_365_25",
        dasha_depth=4,
        include_yogini=True,
        include_ashtottari=True,
        include_chara=True,
    )
    assert (time.perf_counter() - t0) * 1000.0 < 50.0
    assert dasha_res["vimshottari"]["birth_balance"]["lord"] == "Sun"
    assert dasha_res["vimshottari"]["birth_balance"][
        "remaining_years"
    ] == pytest.approx(3.647824, abs=0.01)
    assert "yogini" in dasha_res and len(dasha_res["yogini"]["timeline"]) == 8
    assert "ashtottari" in dasha_res and len(dasha_res["ashtottari"]["timeline"]) == 8
    assert "chara" in dasha_res and len(dasha_res["chara"]["timeline"]) == 12
    assert (
        len(
            json.dumps(compact_vimshottari(dasha_res), ensure_ascii=False).encode(
                "utf-8"
            )
        )
        < 5120
    )


def test_pinda_equal_count_none_cascade_fixed_and_aiyar_profile() -> None:
    signs = {
        "Sun": 0,
        "Moon": 1,
        "Mars": 2,
        "Mercury": 3,
        "Jupiter": 4,
        "Venus": 5,
        "Saturn": 6,
        "Ascendant": 0,
    }
    rao = calculate_rao(signs)
    aiyar = calculate_aiyar(signs)
    assert rao["samudaya_total"] == 337
    assert aiyar["samudaya_total"] == 337
    # Craft equal nonzero pair where sign 0 (Aries) occupied and sign 7 (Scorpio) empty: both values = 4 -> clears empty to 0 (no None)
    occ = {
        p: 0 for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
    }
    row = [4, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0]
    pinda = reduce_pinda(row, occ)
    assert pinda["sodhita"][7] == 0
    assert isinstance(pinda["rasi_pinda"], int)
    assert isinstance(pinda["sodhya_pinda"], int)


@pytest.mark.parametrize("year,month,day,hour", [(2024, 3, 10, 2), (2024, 11, 3, 1)])
def test_dst_nonexistent_and_ambiguous_birth_clocks_rejected(
    year: int, month: int, day: int, hour: int
) -> None:
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


@pytest.mark.native_engine_fault
def test_missing_ephemeris_fails_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    result = calculate_vimshottari(**astro_payload(), analysis_year=2026)
    assert "error" in result and "vimshottari" not in result


def test_parallel_native_positions_are_isolated() -> None:
    birth = build_astro_birth_info(**astro_payload())
    expected = build_india(birth, divisions=[])

    def calculate(i: int):
        if i % 2:
            with runtime.preserve_ephemeris_path():
                runtime.swe.set_sid_mode(runtime.swe.SIDM_FAGAN_BRADLEY)
        return build_india(birth, divisions=[])["charts"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(
            charts == expected["charts"] for charts in pool.map(calculate, range(12))
        )
