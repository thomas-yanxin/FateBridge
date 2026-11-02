"""Explicit geocentric 28-mansion research model for the seven physical 曜.

The catalogue's determinative stars are a declared modern research choice.
Neither this projection nor numerical ephemeris agreement certifies an ancient
boundary system. Calendrical 27-mansion 宿曜 is never derived from these names.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.guolao import mansion_at, positions
from fatebridge.core.suzhan_lunar_phase import lunar_phase_reference

METHOD = "modern_equatorial_research_anchors_v1"


def build_equatorial_mansions(birth: AstroBirthInfo) -> dict[str, Any]:
    if runtime.swe is None:
        raise ImportError("天文不等宽宿度需要Swiss Ephemeris；不静默降级为等分示意。")
    # This projection needs geocentric RA only. Do not evaluate observer
    # geometry or derivative epochs, or invent a site for unused house facts.
    raw = positions(
        birth,
        hsys=0,
        zodiacal=0,
        observer_geometry=False,
        correct_motion=False,
    )
    bodies = []
    for name, state in raw["states"].items():
        bodies.append(
            {
                "id": name,
                "longitude": state["longitude"],
                "latitude": state["latitude"],
                "right_ascension": state["right_ascension"],
                "declination": state["declination"],
                "mansion": mansion_at(state["right_ascension"], raw["boundaries"]),
            }
        )
    return {
        "method_id": METHOD,
        "coordinate_frame": "geocentric_apparent_true_equator_equinox_of_date",
        "coordinate_unit": "modern_degree_360",
        "utc_datetime": birth.utc_isoformat,
        "julian_day_tt": raw["julian_day_tt"],
        "julian_day_ut1": raw["julian_day_ut1"],
        "ephemeris_models": raw["models"],
        "lunar_phase_reference": lunar_phase_reference(raw),
        "catalogue_sha256": raw["catalogue_sha256"],
        "catalogue_sources_sha256": raw["catalogue_sources_sha256"],
        "catalogue_source": "bundled data/guolao/sources.json; CDS SIMBAD astrometry",
        "bodies": bodies,
        "boundaries": raw["boundaries"],
        "coverage": {
            "physical_bodies": list(raw["states"]),
            "derived_points_and_outer_planets": "not_assigned",
        },
        "classical_boundary_acceptance": False,
        "scope": "已声明现代距星与当日视赤经的不等宽宿界；不是唐代宿界复原，不用于农历本命宿。",
    }


def apply_equatorial_mansions(chart: dict[str, Any], astronomy: dict[str, Any]) -> None:
    by_name = {body["id"]: body for body in astronomy["bodies"]}
    for point in chart["objects"]:
        point.pop("su28", None)
        if point["id"] not in by_name:
            point["su28_unavailable_reason"] = "outside_seven_physical_luminaries_scope"
            continue
        body = by_name[point["id"]]
        mansion = body["mansion"]
        point.update(
            su28=mansion["su28"].removesuffix("宿"),
            su28_method=METHOD,
            su28_degree=mansion["degree_in_mansion"],
            su28_width=mansion["mansion_width"],
            right_ascension=body["right_ascension"],
            declination=body["declination"],
            su28_boundary_distance=mansion["boundary_distance"],
        )
