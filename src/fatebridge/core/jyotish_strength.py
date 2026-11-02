"""D1 conditions under the identified R. Santhanam Volume I scan.

This is not a complete Shadbala implementation. In particular, a transformed
varga coordinate is never an input to these physical-longitude calculations.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

SOURCE_ID = "bphs_santhanam_vol1_13609f1a"
SOURCE = {
    "id": SOURCE_ID,
    "title": "Brihat Parasara Hora Sastra, Vol. I, translation and commentary by R. Santhanam, Ranjan Publications (preface dated 1984)",
    "url": "https://elibraryofyoga.com/items/13b2600f-95fd-4bb5-86b4-a18396c68993/full",
    "scan_url": "https://elibraryofyoga.com/bitstreams/0a9652fc-4c10-4904-82bd-7e0c331f1961/download",
    "sha256": "13609f1af89541e070c798b8c70c6bfd74a8b9a71a71388913bf898e9f9ddf3f",
    "sections": [
        "3.49-54: printed pp.38-39",
        "6.5-8, 6.10-15, 6.27-28: printed pp.68-80",
        "27.1-6: printed pp.263-267",
        "27.7: printed p.267; 27.14: printed p.276",
        "27.8-18: printed pp.268-284",
        "45.3-4: printed p.449",
        "7.28-29 commentary: printed p.100",
    ],
    "textual_status": "translator and scanned witness identified; exact reprint edition unconfirmed; sloka translation and translator commentary distinguished; not critical-edition or whole-text acceptance",
    "previous_witness_sha256": "24f5bac882aaa6549a86723c05081703a8d7ec766b97e8fb46a99822efdff758",
}

# Zodiac indexes are zero based. Peaks and zones are distinct concepts:
# Mercury at Virgo 15 degrees is at its peak AND begins its moolatrikona zone.
PEAKS = {
    "Sun": 10.0,
    "Moon": 33.0,
    "Mars": 298.0,
    "Mercury": 165.0,
    "Jupiter": 95.0,
    "Venus": 357.0,
    "Saturn": 200.0,
}
MOOLA = {
    "Sun": (4, 0, 20),
    "Moon": (1, 3, 30),
    "Mars": (0, 0, 12),
    "Mercury": (5, 15, 20),
    "Jupiter": (8, 0, 10),
    "Venus": (6, 0, 15),
    "Saturn": (10, 0, 20),
}
BALADI = ["bala", "kumara", "yuva", "vriddha", "mrita"]
# This is the printed p.100 translator's table, not an unqualified consensus.
# The scan explicitly prints retrograde Mars 8 and Saturn 16 in both columns.
COMBUSTION_ORBS = {
    "Moon": (12, None),
    "Mars": (17, 8),
    "Mercury": (14, 12),
    "Jupiter": (11, 11),
    "Venus": (10, 8),
    "Saturn": (16, 16),
}


def solar_orb_condition(
    planet: str, longitude: float, sun: float, speed: float
) -> dict[str, Any]:
    """An author's angular criterion, without pretending to compute visibility."""
    if planet not in COMBUSTION_ORBS or not all(
        math.isfinite(x) for x in (longitude, sun, speed)
    ):
        raise ValueError(
            "Solar orb criterion requires a registered physical graha and finite coordinates"
        )
    pn, pd = float(longitude).as_integer_ratio()
    sn, sd = float(sun).as_integer_ratio()
    denominator = pd * sd
    delta = (pn * sd - sn * pd) % (360 * denominator)
    distance = min(delta, 360 * denominator - delta)
    direct, retrograde = COMBUSTION_ORBS[planet]
    orb = (
        direct
        if speed > 0
        else retrograde if speed < 0 else direct if direct == retrograde else None
    )
    if orb is None:
        status = (
            "stationary_direction_ambiguous" if speed == 0 else "direction_not_covered"
        )
        within = None
    elif distance == orb * denominator:
        status, within = "at_orb_boundary", None
    else:
        within = distance < orb * denominator
        status = "within_orb" if within else "outside_orb"
    return {
        "status": status,
        "angular_criterion_met": within,
        "sun_longitude_separation_degrees": distance / denominator,
        "orb_degrees": orb,
        "motion_basis": "sign of supplied D1 sidereal longitude rate; zero retained as stationary",
        "source_id": SOURCE_ID,
        "source_section": "7.28-29 translator commentary, printed p.100 / PDF p.99",
        "source_layer": "translator_commentary",
        "rule_id": "jyotish.santhanam_solar_orb.v1",
        "boundary_convention": "strict interior; exact equality reported separately because source does not specify endpoint inclusion",
        "scope": "D1 longitude criterion under this author's table; not heliacal visibility, complete strength, yoga cancellation, real-world incapacity or event probability",
    }


def degree_condition(planet: str, longitude: float) -> dict[str, Any]:
    """Classical zones and one strength component; seven physical grahas only."""
    if planet not in PEAKS:
        raise ValueError(
            "Degree conditions are defined only for the seven physical grahas"
        )
    if not math.isfinite(longitude):
        raise ValueError("Longitude must be finite")
    n, d = float(longitude).as_integer_ratio()
    n %= 360 * d
    sign, remainder = divmod(n, 30 * d)
    m_sign, low, high = MOOLA[planet]
    # All zones use [start,end); integer ratios preserve adjacent float sides.
    if sign == m_sign and low * d <= remainder < high * d:
        zone = "moolatrikona"
    elif planet == "Moon" and sign == 1 and remainder < 3 * d:
        zone = "exaltation_portion"
    elif planet == "Mercury" and sign == 5 and remainder < 15 * d:
        zone = "exaltation_portion"
    elif sign == m_sign:
        zone = "own_sign_portion"
    else:
        zone = "outside_special_degree_zones"
    peak = PEAKS[planet]
    fall = (peak + 180.0) % 360.0
    arc = (Fraction(n, d) - Fraction(fall)) % 360
    distance = min(arc, 360 - arc)
    part = remainder // (6 * d)
    # Aries is odd (index 0), Taurus even (index 1).
    age_index = part if sign % 2 == 0 else 4 - part
    return {
        "source_id": SOURCE_ID,
        "coordinate_scope": "D1 physical sidereal longitude only",
        "degree_zone": zone,
        "zone_rule_id": "jyotish.bphs_degree_zones.v1",
        "boundary_convention": "[start,end); peak longitude is an independent point",
        "deep_exaltation_longitude": peak,
        "deep_debilitation_longitude": fall,
        "uchcha_bala": {
            "value": float(distance / 3),
            "unit": "virupa",
            "maximum": 60.0,
            "rule_id": "jyotish.bphs_uchcha_bala.v1",
            "source_section": "27.1",
            "scope": "one Sthana Bala component; not complete Shadbala, Tajaka 20-point strength or an outcome probability",
        },
        "baladi_avastha": {
            "state": BALADI[age_index],
            "rule_id": "jyotish.bphs_baladi.v1",
            "source_section": "45.3-4",
            "scope": "traditional six-degree condition; no literal age, health, death or lifespan inference",
        },
    }


def physical_state(
    planet: str,
    longitude: float,
    sun: float,
    latitude: float,
    speed: float,
    *,
    native_speed: float | None = None,
    motion_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep computed motion/separation separate from unregistered doctrines."""
    state: dict[str, Any] = {
        "coordinate_scope": "D1 physical ecliptic-of-date coordinates",
        "latitude": latitude,
        "longitude_speed_degrees_per_day": speed,
        "longitude_speed_native_degrees_per_day": (
            speed if native_speed is None else native_speed
        ),
        "motion": (
            "retrograde" if speed < 0 else "direct" if speed > 0 else "stationary"
        ),
        "motion_rule_id": "jyotish.longitude_motion.v2",
    }
    if motion_context is not None:
        state["longitude_motion_context"] = motion_context
    if planet in PEAKS:
        state["degree_condition"] = degree_condition(planet, longitude)
    if planet not in {"Sun", "Rahu", "Ketu"}:
        condition = solar_orb_condition(planet, longitude, sun, speed)
        state["sun_longitude_separation_degrees"] = condition[
            "sun_longitude_separation_degrees"
        ]
        state["combustion"] = condition
    return state
