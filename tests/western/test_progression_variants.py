"""恒星推运 / 赤纬推运 — secondary-progression variants, verified by invariants.

Both techniques run on FateBridge's existing secondary progression, and both are
computed by 星阙/horosa in a closed backend with no readable source and no fixture,
so neither is byte-lockable. We verify each by its defining invariant:

* 恒星推运 (vedicprog): a sidereal secondary progression — every reported aspect's
  separation matches its named angle within orb.
* 赤纬推运 (jaynesprog): declination parallels — every reported pair's declinations
  satisfy the parallel (equal) / contraparallel (equal-and-opposite) relation.
"""

from __future__ import annotations

from fatebridge.core.astrology_lifespan import (
    build_jaynes_declination_payload,
    build_vedic_progression_payload,
)
from fatebridge.services.western_lifespan import (
    calculate_jaynesprog,
    calculate_vedicprog,
)

_ASPECT_ANGLES = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}


def _separation(a: float, b: float) -> float:
    delta = abs((a - b) % 360.0)
    return min(delta, 360.0 - delta)


# --------------------------------------------------------------------------- #
# 恒星推运 (vedicprog) — pure builder invariants.
# --------------------------------------------------------------------------- #
def test_vedic_progression_reports_real_aspects() -> None:
    natal = {"Sun": 10.0, "Moon": 200.0}
    progressed = {
        "Sun": 70.0,
        "Moon": 199.5,
    }  # Sun→Moon? 70 vs 200; Sun sextiles natal Sun
    payload = build_vedic_progression_payload(natal, progressed, orb=1.0)
    for hit in payload["hits"]:
        angle = _ASPECT_ANGLES[hit["aspect"]]
        sep = _separation(
            (
                progressed[hit["source"]]
                if hit["source"] in progressed
                else natal[hit["source"]]
            ),
            natal[hit["target"]],
        )
        assert abs(sep - angle) <= 1.0
    assert payload["zodiac"] == "sidereal"


def test_vedicprog_end_to_end_is_sidereal() -> None:
    result = calculate_vedicprog(
        analysis_year=2026,
        # Pass the inherited field the catalog forwards, to exercise the override path.
        zodiac_type="Tropic",
        house_system="P",
        birth_year=2000,
        birth_month=12,
        birth_day=10,
        birth_hour=9,
        birth_minute=55,
        birth_timezone="Asia/Shanghai",
        birth_longitude=120.45,
        birth_latitude=32.54,
    )
    assert result.get("error") is None, result
    assert result["analysis_context"]["zodiac_type"] == "Sidereal"
    assert result["vedic_progression"]["zodiac"] == "sidereal"


# --------------------------------------------------------------------------- #
# 赤纬推运 (jaynesprog) — pure builder invariants.
# --------------------------------------------------------------------------- #
def test_declination_parallel_and_contraparallel() -> None:
    progressed = {"Sun": 20.0, "Mars": -15.0}
    natal = {"Moon": 20.4, "Venus": 15.2}
    payload = build_jaynes_declination_payload(progressed, natal, orb=0.5)
    pairs = {(p["progressed"], p["natal"], p["kind"]) for p in payload["parallels"]}
    # Sun(+20.0) ∥ Moon(+20.4): same sign, |Δ|=0.4 ≤ 0.5 → parallel.
    assert ("Sun", "Moon", "parallel") in pairs
    # Mars(-15.0) vs Venus(+15.2): opposite sign, |sum|=0.2 ≤ 0.5 → contraparallel.
    assert ("Mars", "Venus", "contraparallel") in pairs
    # Each reported pair genuinely satisfies its declination relation.
    for p in payload["parallels"]:
        if p["kind"] == "parallel":
            assert abs(p["progressed_declination"] - p["natal_declination"]) <= 0.5
        else:
            assert abs(p["progressed_declination"] + p["natal_declination"]) <= 0.5


def test_jaynesprog_end_to_end() -> None:
    result = calculate_jaynesprog(
        analysis_year=2026,
        birth_year=2000,
        birth_month=12,
        birth_day=10,
        birth_hour=9,
        birth_minute=55,
        birth_timezone="Asia/Shanghai",
        birth_longitude=120.45,
        birth_latitude=32.54,
    )
    assert result.get("error") is None, result
    parallels = result["jaynes_declination"]["parallels"]
    orb = result["jaynes_declination"]["orb"]
    for p in parallels:
        if p["kind"] == "parallel":
            assert abs(p["progressed_declination"] - p["natal_declination"]) <= orb
        else:
            assert abs(p["progressed_declination"] + p["natal_declination"]) <= orb
