"""年龄推进点 / Age Point (Huber) — verified by the technique's geometric invariants.

星阙/horosa computes Age Point in a closed backend with no readable source and no
golden fixture, so — unlike 波斯向运 — there is no byte-oracle to lock against. The
Huber technique is, however, fully public and geometrically determined: the point
leaves the Ascendant, sweeps the 12 Koch houses 6 years apiece, and returns to the
Ascendant after 72 years. We verify exactly those invariants on a synthetic chart
(exact cusps, so the assertions are exact) plus a real end-to-end cast.
"""

from __future__ import annotations

from fatebridge.core.astrology_lifespan import build_age_point_payload
from fatebridge.services.western_lifespan import calculate_age_point

# Whole-sign-like synthetic Koch cusps: 12 equal 30° houses from 0° Aries, so the
# age point's position is hand-computable and the invariants assert exact values.
_EQUAL_CUSPS = [i * 30.0 for i in range(12)]


def _point_at(points: list[dict], age: int) -> dict:
    return next(p for p in points if p["age"] == age)


def test_starts_at_ascendant() -> None:
    payload = build_age_point_payload({}, _EQUAL_CUSPS, max_age_years=72.0)
    start = _point_at(payload["points"], 0)
    assert start["longitude"] == 0.0  # the Ascendant (cusp 1)
    assert start["house"] == 1


def test_six_years_per_house_and_cycle_closure() -> None:
    payload = build_age_point_payload({}, _EQUAL_CUSPS, max_age_years=72.0)
    points = payload["points"]
    # 6 years into the cycle the point sits exactly on the 2nd cusp.
    assert _point_at(points, 6)["house"] == 2
    assert _point_at(points, 6)["longitude"] == 30.0
    # Each house spans 6 years; age 36 → house 7 (the Descendant side).
    assert _point_at(points, 36)["house"] == 7
    # After a full 72-year cycle the point returns to the Ascendant.
    assert _point_at(points, 72)["longitude"] == 0.0
    assert _point_at(points, 72)["house"] == 1


def test_equal_house_speed_is_five_degrees_per_year() -> None:
    # 30° house over 6 years ⇒ 5°/year; age 3 is halfway through house 1.
    payload = build_age_point_payload({}, _EQUAL_CUSPS, max_age_years=12.0)
    assert _point_at(payload["points"], 3)["longitude"] == 15.0


def test_conjunction_age_is_exact() -> None:
    # A natal body at 15° Aries (halfway through equal house 1) is reached at age 3.
    payload = build_age_point_payload({"Sun": 15.0}, _EQUAL_CUSPS, max_age_years=72.0)
    contacts = payload["contacts"]
    assert contacts[0]["body"] == "Sun"
    assert contacts[0]["age"] == 3.0
    # The per-year timeline tags age 3 with the Sun conjunction.
    assert _point_at(payload["points"], 3)["aspect_to"] == "Sun"


def test_conjunction_recurs_each_72_year_cycle() -> None:
    payload = build_age_point_payload({"Sun": 15.0}, _EQUAL_CUSPS, max_age_years=80.0)
    sun_ages = [c["age"] for c in payload["contacts"] if c["body"] == "Sun"]
    assert sun_ages == [3.0, 75.0]  # 3 and 3 + 72


# --------------------------------------------------------------------------- #
# End-to-end through FateBridge's own engine (real Koch cast).
# --------------------------------------------------------------------------- #
_BIRTH = dict(
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=9,
    birth_minute=55,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.45,
    birth_latitude=32.54,
)


def test_end_to_end_age_point() -> None:
    # Pass house_system to exercise the Koch override path (catalog forwards it).
    result = calculate_age_point(max_age_years=72.0, house_system="P", **_BIRTH)
    assert result.get("error") is None, result
    payload = result["age_point"]
    points = payload["points"]
    assert len(points) == 73  # ages 0..72 inclusive
    assert points[0]["house"] == 1
    assert points[0]["age"] == 0
    # Real Koch houses are unequal, but the cycle still closes on the Ascendant.
    assert points[72]["longitude"] == points[0]["longitude"]
    assert all(1 <= p["house"] <= 12 for p in points)
    # Forced Koch regardless of any requested house system.
    assert result["analysis_context"]["house_system"] == "K"
