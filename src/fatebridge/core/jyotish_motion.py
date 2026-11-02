"""Frame-labelled angular part of Santhanam27.24-25 / Raman105-107.

This kernel does not supply a mean-position model. In particular the historical
Raman tables are not silently combined with the native Lahiri true positions.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any


def _angle(value: float) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Longitude must be a finite real number in degrees")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Longitude must be a finite real number in degrees")
    return Fraction(value) % 360


def cheshta_arc(
    mean_longitude: float,
    true_longitude: float,
    seeghrochcha: float,
    *,
    mean_frame: str,
    true_frame: str,
    seeghrochcha_frame: str,
) -> dict[str, Any]:
    """Compute the angular stage only, retaining an opposed-midpoint ambiguity.

    Frames are mandatory declarations for all three operands. Equal labels are
    a necessary input contract, not an independent test of their provenance.
    The short-arc midpoint is invariant under a common rotation of the zodiac;
    directly averaging wrapped degrees is not.
    """
    frames = (mean_frame, true_frame, seeghrochcha_frame)
    if any(not isinstance(v, str) or not v.strip() for v in frames):
        raise ValueError("Every longitude requires a nonempty declared frame")
    if len(set(frames)) != 1:
        raise ValueError("Mean, true and Seeghrochcha longitude frames must match")
    mean, true, apogee = map(_angle, (mean_longitude, true_longitude, seeghrochcha))
    delta = (true - mean) % 360
    if delta > 180:
        delta -= 360
    midpoint = (mean + delta / 2) % 360
    opposed = delta == 180
    midpoints = [midpoint, (midpoint + 180) % 360] if opposed else [midpoint]
    branches = []
    for point in midpoints:
        kendra = (apogee - point) % 360
        reduced = min(kendra, 360 - kendra)
        branches.append(
            {
                "midpoint": float(point),
                "directed_kendra": float(kendra),
                "reduced_kendra": float(reduced),
                "virupa": float(reduced / 3),
            }
        )
    return {
        "status": "opposed_midpoint_not_adjudicated" if opposed else "calculated_arc",
        "frame": mean_frame,
        "value": None if opposed else branches[0]["virupa"],
        "unit": "virupa",
        "branches": branches,
        "rule_id": "jyotish.cheshta_arc.v1",
        "source_sections": ["Santhanam27.24-25", "Raman105-107"],
        "scope": "Angular stage only; common frame declarations do not validate the mean-position model, its epoch, original-text acceptance or real-world prediction",
        "midpoint_convention": "shortest circular arc; exactly180deg retains both midpoints without selecting a larger strength",
    }
