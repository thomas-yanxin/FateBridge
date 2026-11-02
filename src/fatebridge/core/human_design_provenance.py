"""Declared Swiss flag convention for Human Design positions.

The public swephexp.h bits are stable: JPL=1, Swiss=2, Moshier=4, SPEED=256.
Other bits change the requested coordinate, target or speed convention and
are not part of this ruleset. A valid flag is not proof of celestial accuracy.
Source: https://www.astro.com/swisseph/swephprg.htm, sections 3.3 and 3.5.
"""

MODEL_BITS = {1: "jpl", 2: "swieph", 4: "moshier"}
SPEED_BIT = 256


def position_flag_model(flags: object, *, require_speed: bool = True) -> str:
    """Require one backend and the declared ecliptic-of-date convention."""
    if type(flags) is not int or flags < 0:
        raise ValueError("Invalid Swiss position flag type or error value")
    model_bits = flags & 7
    if model_bits not in MODEL_BITS or flags & ~(7 | SPEED_BIT):
        raise ValueError("Swiss flags do not match the declared HD position convention")
    if require_speed and not flags & SPEED_BIT:
        raise ValueError("Swiss flags do not report the requested position speed")
    return MODEL_BITS[model_bits]
