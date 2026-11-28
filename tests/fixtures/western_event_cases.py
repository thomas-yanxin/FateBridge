"""Shared Western election and horary regression cases."""

from types import SimpleNamespace

from pydantic import JsonValue

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.lilly_house_assignment import HOUSE_ATTRIBUTES

CANDIDATE = dict(
    candidate_year=2025,
    candidate_month=3,
    candidate_day=15,
    candidate_hour=10,
    candidate_minute=0,
    timezone_name="Asia/Shanghai",
    longitude=116.4,
    latitude=39.9,
)


QUESTION = dict(
    question_year=2024,
    question_month=6,
    question_day=1,
    question_hour=14,
    question_minute=30,
    timezone_name="Asia/Shanghai",
    longitude=116.4,
    latitude=39.9,
)


def state(planet: str, longitude: float, speed: float | None) -> dict[str, JsonValue]:
    return {
        "planet": planet,
        "planet_label": planet,
        "longitude": longitude,
        "speed": speed,
        "sign": "Aries",
        "sign_label": "白羊",
        "dignities": [],
    }


def synthetic_subject(**changes: tuple[float, float | None]) -> SimpleNamespace:
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
    for i, attr in enumerate(HOUSE_ATTRIBUTES):
        points.setdefault(attr, SimpleNamespace(abs_pos=float(i * 30), sign=SIGNS[i]))
    return SimpleNamespace(
        **points,
        julian_day_tt=2451545.0,
        zodiac_type="Tropical",
        is_diurnal=True,
        calculation_basis={"julian_day_tt": 2451545.0},
    )


def event_result(voc: bool | None = False) -> dict[str, JsonValue]:
    return {
        "status": "unavailable" if voc is None else "computed",
        "method_id": "native_tt_lunar_contacts_before_ingress_v1",
        "constant_velocity_projection": False,
        "void_of_course": voc,
        "contacts": [],
        "start_julian_day_tt": 2451545.0,
    }
