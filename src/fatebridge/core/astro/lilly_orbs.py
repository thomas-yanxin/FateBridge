"""The two full-orb columns printed on Lilly 1647 p.107.

These are full orbs, not moieties or the p.113 solar-condition thresholds.
The first column is the default: its Saturn/Venus moieties reproduce the
printed example. Lilly explicitly permits both columns; neither is fitted
to a desired judgement. Equality is a disclosed implementation convention.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

OrbProfile = Literal["lilly_1647_p107_first", "lilly_1647_p107_second"]
DEFAULT_ORB_PROFILE: OrbProfile = "lilly_1647_p107_first"
SOURCE_URL = "https://wellcomecollection.org/works/s7z7c46y"
_FULL_ORBS = {
    "lilly_1647_p107_first": {
        "Saturn": 10.0,
        "Jupiter": 12.0,
        "Mars": 7.5,
        "Sun": 17.0,
        "Venus": 8.0,
        "Mercury": 7.0,
        "Moon": 12.5,
    },
    "lilly_1647_p107_second": {
        "Saturn": 9.0,
        "Jupiter": 9.0,
        "Mars": 7.0,
        "Sun": 15.0,
        "Venus": 7.0,
        "Mercury": 7.0,
        "Moon": 12.0,
    },
}


def full_orbs(profile: str = DEFAULT_ORB_PROFILE) -> dict[str, float]:
    if profile not in _FULL_ORBS:
        raise ValueError("Unknown Lilly orb_profile; select a printed p107 column")
    return dict(_FULL_ORBS[profile])


def pair_radius(
    first: str, second: str, profile: str = DEFAULT_ORB_PROFILE
) -> Fraction:
    table = full_orbs(profile)
    return (Fraction(table[first]) + Fraction(table[second])) / 2


def orb_receipt(profile: str = DEFAULT_ORB_PROFILE) -> dict:
    table = full_orbs(profile)
    return {
        "profile_id": profile,
        "source_url": SOURCE_URL,
        "source_pages": [107],
        "full_orbs_degrees": table,
        "moieties_degrees": {planet: value / 2 for planet, value in table.items()},
        "available_profiles": list(_FULL_ORBS),
        "pair_rule": "half_sum_of_full_orbs",
        "boundary_convention": "closed_exact_binary_input_before_rounding; equality is an implementation convention, not a textual certainty",
        "default_selection_basis": "First printed column; Saturn 5 and Venus 4 degree moieties reproduce the printed example. Both printed columns remain valid source variants.",
        "full_original_text_acceptance": False,
    }
