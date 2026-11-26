"""Classical ephemeris tests: retrograde, out-of-bounds, prenatal
syzygy, and Almuten Figuris (命主).

Two layers:
* **Pure** derivations (``is_retrograde`` / ``out_of_bounds`` / ``build_almuten_figuris``)
  are tested directly — no ephemeris needed, so they run everywhere.
* **Integration** invariants (real planet speed / declination / the backward
  syzygy search) are gated on swisseph being importable; they pin the Dec-2000
  natal chart against the actual sky (Jupiter + Saturn retrograde; the prenatal
  New Moon ~14 days before birth).

Not a byte-oracle: correctness is pinned by classical invariants + real-sky
facts, matching the rest of the 古典 layer (the chart service is backend-computed).
"""

from __future__ import annotations

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.classical_western import (
    build_almuten_figuris,
    build_planet_classical,
    is_retrograde,
    out_of_bounds,
)
from fatebridge.core.contracts.output_charts import AlmutenFiguris
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.astrology_classical_snapshot import _build_almuten_figuris_line

_SWE_AVAILABLE = swe is not None
_requires_swe = pytest.mark.skipif(
    not _SWE_AVAILABLE, reason="swisseph 不可用：逆行/出界/朔望需要星历"
)

# 颜鑫 (左右) 本人命盘 — 跨体系交叉验证的基准案例 (真太阳时已开启).
_NATAL = dict(
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=9,
    birth_minute=55,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.4667,
    birth_latitude=32.5417,
    name="左右",
    birth_place="海安",
)


# ── pure: retrograde / out-of-bounds ──────────────────────────────────────────


def test_is_retrograde_sign_of_speed() -> None:
    assert is_retrograde(-0.001) is True
    assert is_retrograde(0.5) is False
    # Exactly stationary counts as direct (not yet crossed into retrograde).
    assert is_retrograde(0.0) is False


def test_is_retrograde_unknown_speed_is_none() -> None:
    # Offline approximate engine supplies no speed → "unknown", never fabricated.
    assert is_retrograde(None) is None


def test_out_of_bounds_brackets_the_solar_limit() -> None:
    assert out_of_bounds(23.41, 23.4) is True
    assert out_of_bounds(-23.41, 23.4) is True  # symmetric
    assert out_of_bounds(23.39, 23.4) is False
    assert out_of_bounds(0.0, 23.4) is False


def test_out_of_bounds_unknown_declination_is_none() -> None:
    assert out_of_bounds(None) is None
    assert out_of_bounds(24.0) is None


def test_build_planet_classical_degrades_without_ephemeris() -> None:
    # No speed / declination passed (the swe-is-None path): both flags unknown.
    entry = build_planet_classical(
        planet="Mars",
        sign="Aries",
        degree_in_sign=10.0,
        longitude=10.0,
        house=1,
        sun_longitude=15.0,
        chart_sect="day",
    )
    assert entry["retrograde"] is None
    assert entry["out_of_bounds"] is None


def test_build_planet_classical_threads_speed_and_declination() -> None:
    entry = build_planet_classical(
        planet="Saturn",
        sign="Taurus",
        degree_in_sign=12.0,
        longitude=42.0,
        house=4,
        sun_longitude=250.0,
        chart_sect="day",
        longitude_speed=-0.05,
        declination=25.0,
        obliquity=23.4,
    )
    assert entry["retrograde"] is True
    assert entry["out_of_bounds"] is True


# ── pure: Almuten Figuris ─────────────────────────────────────────────────────


def test_almuten_figuris_sums_dignities_across_points() -> None:
    # Aries throughout, daytime: Mars (domicile 5 + triplicity... ) and the term/
    # face lords accumulate. The winner must be the planet with the largest
    # cross-point total, and that total must equal the max in `totals`.
    points = {
        "Sun": {"sign": "Aries", "degree_in_sign": 5.0},
        "Moon": {"sign": "Aries", "degree_in_sign": 5.0},
        "Ascendant": {"sign": "Aries", "degree_in_sign": 5.0},
    }
    result = build_almuten_figuris(points, is_day=True)
    assert result["winner"] is not None
    assert result["totals"][result["winner"]] == max(result["totals"].values())
    assert set(result["points"]) == {"Sun", "Moon", "Ascendant"}


def test_almuten_figuris_skips_missing_points() -> None:
    # Only the points supplied count — a syzygy-less (offline) chart still elects.
    points = {"Sun": {"sign": "Leo", "degree_in_sign": 0.0}}
    result = build_almuten_figuris(points, is_day=True)
    # Leo 0°: Sun rules (domicile 5) → Sun must lead.
    assert result["winner"] == "Sun"
    assert list(result["points"]) == ["Sun"]


def test_almuten_figuris_empty_is_none() -> None:
    result = build_almuten_figuris({}, is_day=True)
    assert result["winner"] is None
    assert result["totals"] == {}


def test_almuten_figuris_tie_breaks_to_slower_planet() -> None:
    # Construct a symmetric tie and confirm the Chaldean (slowest-first) winner is
    # deterministic across repeated builds.
    points = {
        "Sun": {"sign": "Aries", "degree_in_sign": 5.0},
        "Moon": {"sign": "Libra", "degree_in_sign": 5.0},
    }
    first = build_almuten_figuris(points, is_day=True)["winner"]
    second = build_almuten_figuris(points, is_day=True)["winner"]
    assert first == second


@pytest.mark.parametrize(
    "included,missing",
    [
        (("Sun", "Moon", "Ascendant", "fortune", "syzygy"), ()),
        (("Sun", "Moon", "Ascendant", "fortune"), ("syzygy",)),
        (("Sun",), ("Moon", "Ascendant", "fortune", "syzygy")),
        ((), ("Sun", "Moon", "Ascendant", "fortune", "syzygy")),
    ],
)
def test_almuten_figuris_method_delivery_and_projection(included, missing) -> None:
    # Synthetic input-coverage shapes, not physical charts or a numeric oracle.
    result = build_almuten_figuris(
        {point: {"sign": "Aries", "degree_in_sign": 5.0} for point in included},
        is_day=True,
    )
    method = result["method"]
    assert method["included_points"] == list(included)
    assert method["missing_points"] == list(missing)
    assert method["source_profile"] == "mixed_dorothean_egyptian_lilly"
    assert method["is_day"] is True
    assert method["historical_method_status"] == "selected_mixed_subset"
    assert method["source_refs"]
    assert all(reference["scope"] for reference in method["source_refs"])
    AlmutenFiguris.model_validate(result)

    projected = AlmutenFiguris.model_validate(
        {"method": {"missing_points": list(missing)}}
    )
    assert projected.model_fields_set == {"method"}
    assert projected.method is not None
    assert projected.method.model_fields_set == {"missing_points"}
    assert projected.method.missing_points == list(missing)
    assert projected.method.is_day is None

    text = _build_almuten_figuris_line({"classical": {"almuten_figuris": result}})
    assert f"本次{len(included)}个可得点的本质尊贵汇总" in text
    assert "固定Chaldean顺序" in text
    assert "完整历史命主程序未认证" in text
    labels = {
        "Sun": "日",
        "Moon": "月",
        "Ascendant": "命",
        "fortune": "福",
        "syzygy": "朔望",
    }
    if missing:
        expected_missing = (
            "未纳入点：" + "、".join(labels[point] for point in missing) + "。"
        )
        assert expected_missing in text
    else:
        assert "未纳入点：" not in text
    assert ("无可用参与点。" in text) == (not included)


# ── integration: real ephemeris invariants on the natal chart ─────────────────


@pytest.fixture(scope="module")
def natal_chart():
    info = build_astro_birth_info(use_true_solar_time=True, **_NATAL)
    return build_core_chart_payload(info, "hellen_chart")


@_requires_swe
def test_every_planet_has_retro_and_oob_flags(natal_chart) -> None:
    for entry in natal_chart["classical"]["planets"].values():
        assert "retrograde" in entry and isinstance(entry["retrograde"], bool)
        assert "out_of_bounds" in entry and isinstance(entry["out_of_bounds"], bool)


@_requires_swe
def test_dec_2000_jupiter_and_saturn_are_retrograde(natal_chart) -> None:
    # Real sky: both outer benefic/malefic were retrograde in Dec 2000.
    planets = natal_chart["classical"]["planets"]
    assert planets["Jupiter"]["retrograde"] is True
    assert planets["Saturn"]["retrograde"] is True
    # Luminaries never retrograde.
    assert planets["Sun"]["retrograde"] is False
    assert planets["Moon"]["retrograde"] is False


@_requires_swe
def test_prenatal_syzygy_precedes_birth_and_is_a_lunation(natal_chart) -> None:
    info = build_astro_birth_info(use_true_solar_time=True, **_NATAL)
    birth_jd = _julian_day(info.utc_datetime)
    syzygy = natal_chart["classical"]["syzygy"]
    assert syzygy is not None
    assert syzygy["type"] in {"new", "full"}
    # Strictly before birth, and within one synodic month (~29.5 days).
    assert syzygy["julian_day"] < birth_jd
    assert birth_jd - syzygy["julian_day"] < 30.0
    # Dec-2000 birth → the prenatal lunation was the 2000-11-25 New Moon.
    assert syzygy["type"] == "new"
    assert syzygy["sign"] == "Sagittarius"


@_requires_swe
def test_almuten_figuris_uses_five_points_and_winner_leads(natal_chart) -> None:
    figuris = natal_chart["classical"]["almuten_figuris"]
    # With swe present all five hylegic points resolve.
    assert set(figuris["points"]) == {
        "Sun",
        "Moon",
        "Ascendant",
        "fortune",
        "syzygy",
    }
    winner = figuris["winner"]
    assert winner is not None
    assert figuris["totals"][winner] == max(figuris["totals"].values())


@_requires_swe
def test_snapshot_renders_mingzhu_section_and_retrograde() -> None:
    payload = calculate_core_chart_analysis(
        chart_variant="hellen_chart", use_true_solar_time=True, **_NATAL
    )
    text = payload["snapshot_text"]
    assert "[命主]" in text
    assert "命主：" in text
    assert "朔望：" in text
    # Jupiter/Saturn retrograde must surface in the 古典 section.
    assert "逆行" in text
