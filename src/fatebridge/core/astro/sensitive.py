"""Sensitive-point equivalence from Udo Rudolph's 1996 published excerpt.

Printed p.14 equates MA+JU-ZE=MC with MC/ZE=MA/JU. When a midpoint
equation is reduced modulo P, its sum equation is reduced modulo 2P.
Failing to double the period or the orb changes the mathematical claim.
"""

import hashlib
import json
import math
from fractions import Fraction
from typing import Any, Dict, Mapping, Optional

SOURCE: Dict[str, Any] = {
    "id": "udo_rudolph_1996_abc_excerpt",
    "author": "Udo Rudolph",
    "title": "ABC fuer Planetenbilder, first German edition 1996, ISBN 3-00-000881-0",
    "url": "https://witte-verlag.com/component/djcatalog2/?fid=12&format=raw&task=download",
    "sections": ["printed p.14; publisher excerpt PDF p.6"],
    "source_sha256": "fd05ac9597cfc955b0f32c377a69dfe170b282616812c802b386b6b7172ccfd7",
    "scope": "Published symbolic sensitive-point example; excerpt, not the complete book or an empirical outcome study",
}


def _delta(first: Fraction, second: Fraction, period: int) -> Fraction:
    return (first - second + Fraction(period, 2)) % period - Fraction(period, 2)


def _display_angle(value: Fraction) -> float:
    result = float(value % 360)
    return min(result, math.nextafter(360.0, 0.0))


def sensitive_equivalence(
    a: str,
    b: str,
    c: str,
    d: str,
    values: Mapping[str, Fraction],
    *,
    midpoint_period: int,
    midpoint_orb: Fraction,
) -> Dict[str, Any]:
    """Equivalent occupied sensitive point for one actual four-factor contact.

    The returned folded relation need not be a direct conjunction. Direct
    occupancy is assessed separately in the full 360-degree circle.
    """
    point = (values[a] + values[b] - values[c]) % 360
    period = midpoint_period * 2
    folded = _delta(point, values[d], period)
    direct = _delta(point, values[d], 360)
    return {
        "plus": [a, b],
        "minus": c,
        "occupant": d,
        "equation": f"{a}+{b}-{c}={d}",
        "longitude": _display_angle(point),
        "occupant_longitude": _display_angle(values[d]),
        "period_degrees": period,
        "signed_orb": float(folded),
        "orb": float(abs(folded)),
        "maximum_orb_degrees": float(midpoint_orb * 2),
        "direct_signed_orb": float(direct),
        "direct_orb": float(abs(direct)),
        "occupancy": "direct" if abs(direct) <= midpoint_orb * 2 else "folded_only",
        "rule_id": "hamburg.sensitive_point_equivalence.v1",
    }


def original_example_reading(
    a: str,
    b: str,
    c: str,
    d: str,
    values: Mapping[str, Fraction],
    *,
    axis_orb: Fraction,
) -> Optional[Dict[str, Any]]:
    """Interpret only the actual source-authored symbolic pattern when occupied.

    The source excerpt does not license an invented keyword dictionary for
    other patterns. No claim is made that this symbolic reading predicts events.
    """
    pairs = {frozenset((a, b)), frozenset((c, d))}
    if pairs != {frozenset(("Mars", "Jupiter")), frozenset(("Zeus", "Midheaven"))}:
        return None
    point = (values["Mars"] + values["Jupiter"] - values["Zeus"]) % 360
    direct = _delta(point, values["Midheaven"], 360)
    if abs(direct) > axis_orb * 2:
        return None
    basis = [
        [name, values[name].numerator, values[name].denominator]
        for name in ("Mars", "Jupiter", "Zeus", "Midheaven")
    ]
    claim_id = hashlib.sha256(
        json.dumps([basis, str(axis_orb)], separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "claim_id": claim_id,
        "factor_longitudes": {
            name: _display_angle(values[name])
            for name in ("Mars", "Jupiter", "Zeus", "Midheaven")
        },
        "contains_hypothetical": True,
        "source_id": SOURCE["id"],
        "source_section": "printed p.14",
        "source_expression": "MA+JU-ZE=MC; MC/ZE=MA/JU",
        "basis_expression": "Mars+Jupiter-Zeus=Midheaven",
        "sensitive_point_longitude": _display_angle(point),
        "occupant_longitude": _display_angle(values["Midheaven"]),
        "direct_orb_degrees": float(abs(direct)),
        "maximum_orb_degrees": float(axis_orb * 2),
        "symbolic_theme_zh": "以行动取得成效的个人目标",
        "reading_zh": "依该书的象征解释，可围绕个人目标及行动成效讨论；这不是现实成功保证。",
        "practical_prompt_zh": "结合现实资料核对当前目标、实际行动和成效标准。",
        "claim_type": "source_attributed_symbolic_interpretation",
        "rule_id": "hamburg.udo1996.symbolic_example.v1",
    }
