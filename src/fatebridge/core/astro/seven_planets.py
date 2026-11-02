"""Seven-planet 360-degree midpoint view computed before display rounding."""

import math
from fractions import Fraction
from typing import Any, Dict, List

from fatebridge.core.astro.reference import _TRADITIONAL_PLANET_IDS, ASPECTS
from fatebridge.core.astrology_tables import SIGN_LABELS_ZH, SIGNS


def _display(value: Fraction, period: int = 360) -> float:
    value %= period
    result = float(value)
    return math.nextafter(result, -math.inf) if Fraction(result) > value else result


def seven_planet_view(factors: List[Dict[str, Any]]) -> Dict[str, Any]:
    bodies = [factor for factor in factors if factor["id"] in _TRADITIONAL_PLANET_IDS]
    values = {factor["id"]: Fraction(factor["longitude"]) % 360 for factor in bodies}
    midpoints, contacts = [], []
    for index, first in enumerate(bodies):
        a = values[first["id"]]
        for second in bodies[index + 1 :]:
            b = values[second["id"]]
            delta = (b - a) % 360
            antipodal = delta == 180
            if delta > 180:
                delta -= 360
            # Exact antipodal points have two equally valid midpoints. Use a
            # canonical axis, publish both, and do not let factor order choose.
            midpoint = ((a + b) / 2) % 180 if antipodal else (a + delta / 2) % 360
            sign = SIGNS[int(midpoint // 30)]
            midpoints.append(
                {
                    "id_a": first["id"],
                    "id_b": second["id"],
                    "longitude": _display(midpoint),
                    "sign": sign,
                    "sign_zh": SIGN_LABELS_ZH[sign],
                    "degree_in_sign": _display(midpoint, 30),
                    "opposite_longitude": _display(midpoint + 180),
                    "antipodal_inputs": antipodal,
                    "computed_from_unrounded": True,
                }
            )
            for planet in bodies:
                separation = abs(values[planet["id"]] - midpoint) % 360
                separation = min(separation, 360 - separation)
                for name, angle in ASPECTS:
                    orb = abs(separation - Fraction(angle))
                    if orb <= 2:
                        contacts.append(
                            {
                                "planet": planet["id"],
                                "midpoint": f"{first['id']}/{second['id']}",
                                "aspect": name,
                                "orb": float(orb),
                            }
                        )
                        break
    # Preserve the existing planet-major / midpoint-minor public ordering.
    body_order = {body["id"]: index for index, body in enumerate(bodies)}
    midpoint_order = {
        f"{row['id_a']}/{row['id_b']}": index for index, row in enumerate(midpoints)
    }
    contacts.sort(
        key=lambda row: (body_order[row["planet"]], midpoint_order[row["midpoint"]])
    )
    return {"midpoints": midpoints, "midpoint_aspects": contacts}
