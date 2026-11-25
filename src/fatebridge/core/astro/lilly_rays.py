"""Caster-directed sign tables in Lilly's 1647 edition, pp108–109.

These sign relations supplement an independently selected degree/orb aspect.
They neither change that selection nor certify an event or a judgement.
The sixteen pairs absent from both printed tables stay unclassified here.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.geometry import angle_fraction

METHOD_ID = "lilly1647_p108_109_directed_sign_tables_v1"
SOURCE_URL = "https://wellcomecollection.org/works/s7z7c46y"

# Literal p109 inconjunct column, in zodiac order. Do not complete this table
# with every adjacent/quincunx sign, or infer positive relations from omissions.
INCONJUNCT = (
    ("Taurus", "Scorpio"),
    ("Aries", "Gemini", "Libra", "Sagittarius"),
    ("Taurus", "Scorpio"),
    ("Leo", "Aquarius"),
    ("Cancer", "Virgo", "Capricorn", "Pisces"),
    ("Leo", "Aquarius"),
    ("Scorpio", "Taurus"),
    ("Libra", "Sagittarius", "Aries", "Gemini"),
    ("Scorpio", "Taurus"),
    ("Aquarius", "Leo"),
    ("Capricorn", "Pisces", "Cancer", "Virgo"),
    ("Aquarius", "Leo"),
)

# p108: succession is sinister; against succession is dexter. Opposition is
# one undivided printed column and is not assigned a left/right direction.
RAYS = {
    2: ("sextile", "sinister"),
    3: ("square", "sinister"),
    4: ("trine", "sinister"),
    6: ("opposition", None),
    8: ("trine", "dexter"),
    9: ("square", "dexter"),
    10: ("sextile", "dexter"),
}


def directed_sign_relationship(
    caster: str,
    caster_longitude: float,
    receiver: str,
    receiver_longitude: float,
    *,
    selected_degree_aspect: str | None = None,
    zodiac_type: str | None = None,
) -> dict[str, Any]:
    """Read exact half-open sign cells of the supplied finite longitudes.

    Caster/receiver is the direction of a ray, not reception's host/guest.
    A same-sign bodily configuration is distinct from a sign ray (p106).
    No rounding, tolerance band or extra observational precision is introduced.
    """
    first = int((angle_fraction(caster_longitude) % 360) // 30)
    second = int((angle_fraction(receiver_longitude) % 360) // 30)
    steps = (second - first) % 12
    caster_sign, receiver_sign = SIGNS[first], SIGNS[second]
    ray, direction = RAYS.get(steps, (None, None))
    listed = receiver_sign in INCONJUNCT[first]
    status = (
        "ray"
        if ray
        else (
            "co_present"
            if steps == 0
            else "listed_inconjunct" if listed else "not_in_either_table"
        )
    )
    agrees = None
    if selected_degree_aspect is not None and status != "not_in_either_table":
        agrees = selected_degree_aspect == ("conjunction" if steps == 0 else ray)
    else:
        pass
    return {
        "method_id": METHOD_ID,
        "caster": caster,
        "receiver": receiver,
        "caster_sign": caster_sign,
        "receiver_sign": receiver_sign,
        "forward_sign_steps": steps,
        "distinct_bodies": caster != receiver,
        "relation_status": status,
        "sign_ray": ray,
        "ray_direction": direction,
        "listed_inconjunct": listed,
        "selected_degree_aspect": selected_degree_aspect,
        "selected_degree_aspect_agrees": agrees,
        "coordinate_scope": (
            "tropical_selected_edition"
            if zodiac_type in {"Tropic", "Tropical"}
            else (
                "sidereal_extension_not_original_edition_acceptance"
                if zodiac_type == "Sidereal"
                else "coordinate_system_not_qualified"
            )
        ),
        "source_pages": [106, 108, 109],
        "source_url": SOURCE_URL,
        "boundary_policy": "exact_supplied_longitudes_half_open_30_degree_signs",
        "direction_policy": "caster_to_receiver; opposition_column_undivided",
        "quantitative_bonus_added": False,
        "full_original_text_acceptance": False,
    }
