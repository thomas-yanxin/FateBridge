"""Source-epoch light cone, with exact signs for supplied binary64 positions.

For a continuous subluminal source F(e)=e-observation+distance(e)/c increases.
Its supplied finite samples need to support an adjacent source-epoch bracket;
neither fixed-point equality nor a rounded residual certifies the root. This
is a numerical source receipt, not a physical TT/TDB or dynamics certificate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Generic, Sequence, TypeVar

from fatebridge.utils.errors import EphemerisSourceError

LIGHT_SPEED_AU_DAY_EXACT = Fraction(299792458 * 86400, 149597870700)
LIGHT_SPEED_AU_DAY = float(LIGHT_SPEED_AU_DAY_EXACT)
Payload = TypeVar("Payload")


@dataclass(frozen=True)
class RetardedSample(Generic[Payload]):
    epoch: float
    coordinates: tuple[float, ...]
    payload: Payload
    distance: float
    residual_squared: Fraction
    delay: Fraction


@dataclass(frozen=True)
class LightConeSolution(Generic[Payload]):
    lower: RetardedSample[Payload]
    upper: RetardedSample[Payload]
    iterations: int


def solve_light_cone(
    observation: float,
    observer: Sequence[float],
    sample: Callable[[float], tuple[tuple[float, ...], Payload]],
) -> LightConeSolution[Payload]:
    """Bracket F at adjacent representable epochs on the declared source clock."""
    emission = observation
    lower: RetardedSample[Payload] | None = None
    upper: RetardedSample[Payload] | None = None
    for iteration in range(20):
        coordinates, payload = sample(emission)
        ray = [coordinates[i] - observer[i] for i in range(3)]
        distance = math.hypot(*ray)
        distance_squared = sum(
            ((Fraction(coordinates[i]) - Fraction(observer[i])) ** 2 for i in range(3)),
            Fraction(),
        )
        delay = Fraction(observation) - Fraction(emission)
        residual = distance_squared - (LIGHT_SPEED_AU_DAY_EXACT * delay) ** 2
        current = RetardedSample(
            emission, coordinates, payload, distance, residual, delay
        )
        if residual == 0:
            lower = upper = current
            break
        if residual < 0:
            lower = current
        else:
            upper = current
        if (
            lower is not None
            and upper is not None
            and math.nextafter(lower.epoch, math.inf) == upper.epoch
        ):
            break
        # Use the same exact source differences as the sign test. Subtracting
        # an independently rounded distance/c from observation can miss a fine
        # elapsed-epoch root by many ULPs. Rationalize F before updating e.
        denominator = LIGHT_SPEED_AU_DAY_EXACT * (
            Fraction(distance) + LIGHT_SPEED_AU_DAY_EXACT * delay
        )
        proposal = float(Fraction(emission) - residual / denominator)
        if (residual < 0 and proposal <= emission) or (
            residual > 0 and proposal >= emission
        ):
            proposal = math.nextafter(emission, math.inf if residual < 0 else -math.inf)
        if (
            lower is not None
            and upper is not None
            and not lower.epoch < proposal < upper.epoch
        ):
            proposal = lower.epoch + (upper.epoch - lower.epoch) / 2
        emission = proposal
    else:
        raise EphemerisSourceError("light_cone_not_bracketed")
    assert lower is not None and upper is not None
    return LightConeSolution(lower, upper, iteration + 1)
