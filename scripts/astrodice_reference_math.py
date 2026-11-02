"""Portable high-precision replay of the reference's binary64 radian inputs.

This is an arithmetic check of stored directions, not an ephemeris oracle or
an observational error bound. It avoids treating one platform's libm as truth.
"""

import math
from decimal import Decimal, localcontext

PRECISION = 110
COMPONENT_ULP_BUDGET = 4
ARITHMETIC_FLOOR = Decimal("1e-90")


def sine_cosine(argument):
    """Taylor replay for |x|<=7 with a tail far below binary64 resolution.

    After the first few terms the alternating tail decreases. Up to160
    terms,110decimal digits and a1e-102 final term leave a generous1e-90
    arithmetic floor. The fixed range covers the protocol's RA/DEC arguments.
    """
    if not math.isfinite(argument) or abs(argument) > 7:
        raise ValueError("Reference radian argument outside replay domain")
    with localcontext() as context:
        context.prec = PRECISION
        x = Decimal.from_float(argument)
        square = -(x * x)
        sine_term, cosine_term = x, Decimal(1)
        sine, cosine = sine_term, cosine_term
        for n in range(1, 161):
            sine_term *= square / Decimal((2 * n) * (2 * n + 1))
            cosine_term *= square / Decimal((2 * n - 1) * (2 * n))
            sine += sine_term
            cosine += cosine_term
            if max(abs(sine_term), abs(cosine_term)) < Decimal("1e-102"):
                return sine, cosine
    raise ValueError("High-precision reference replay did not converge")


def precise_direction(ra_degrees, dec_degrees):
    if not (math.isfinite(ra_degrees) and math.isfinite(dec_degrees)):
        raise ValueError("Nonfinite reference angle")
    if not 0 <= ra_degrees < 360 or not -90 <= dec_degrees <= 90:
        raise ValueError("Reference angle outside RA/DEC domain")
    # Preserve the collector's public binary64 degree-to-radian conversion.
    # Only the sin/cos implementation is independently replaced here.
    sine_alpha, cosine_alpha = sine_cosine(math.radians(ra_degrees))
    sine_delta, cosine_delta = sine_cosine(math.radians(dec_degrees))
    with localcontext() as context:
        context.prec = PRECISION
        return [cosine_delta * cosine_alpha, cosine_delta * sine_alpha, sine_delta]


def check_stored_direction(stored, truth):
    if len(stored) != 3 or not all(math.isfinite(v) for v in stored):
        raise ValueError("Invalid stored direction shape/values")
    maximum = 0.0
    with localcontext() as context:
        context.prec = PRECISION
        for value, exact in zip(stored, truth):
            ulp = Decimal.from_float(math.ulp(float(exact)))
            error = abs(Decimal.from_float(value) - exact)
            if error > COMPONENT_ULP_BUDGET * ulp + ARITHMETIC_FLOOR:
                raise ValueError("Stored direction exceeds mathematical replay budget")
            maximum = max(maximum, float(error / ulp))
    return maximum
