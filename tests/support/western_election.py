"""Synthetic election controls independent of optional astronomy references."""

from types import SimpleNamespace

import fatebridge.core.astrology_horary as horary


def synthetic_subject(**changes):
    rows = {
        "sun": (310, 1),
        "moon": (55, 13),
        "mercury": (280, 1.2),
        "venus": (230, 1),
        "mars": (105, 0.5),
        "jupiter": (345, 0.08),
        "saturn": (210, 0.03),
        "ascendant": (70, None),
        "medium_coeli": (160, None),
        "first_house": (60, None),
        "tenth_house": (150, None),
    }
    rows.update(changes)
    points = {
        p: SimpleNamespace(
            abs_pos=float(lon), speed=speed, sign="Aries", house="First_House"
        )
        for p, (lon, speed) in rows.items()
    }
    for i, attr in enumerate(horary.HOUSE_ATTRIBUTES):
        points.setdefault(
            attr, SimpleNamespace(abs_pos=float(i * 30), sign=horary.SIGNS[i])
        )
    return SimpleNamespace(
        **points,
        julian_day_tt=2451545.0,
        zodiac_type="Tropical",
        is_diurnal=True,
        calculation_basis={"julian_day_tt": 2451545.0},
    )


def event_result(voc=False):
    return {
        "status": "unavailable" if voc is None else "computed",
        "method_id": "native_tt_lunar_contacts_before_ingress_v1",
        "constant_velocity_projection": False,
        "void_of_course": voc,
        "contacts": [],
        "start_julian_day_tt": 2451545.0,
    }
