"""Drive the current root solver with controlled, exactly declared trajectories.

This supplies observations for reader tests, never their expected answers or
an independent physical ephemeris reference.
"""

from fractions import Fraction

from fatebridge.core.horary_motion import solve_lunar_contacts


def sampled_motion(moon, others):
    states = {"Moon": moon}
    states.update(
        (row.get("planet", f"target_{i}"), row) for i, row in enumerate(others)
    )

    def sample(planet, at):
        row = states[planet]
        return {
            "longitude": float(
                Fraction(row["longitude"]) + Fraction(row["speed"]) * Fraction(at)
            ),
            "speed": row["speed"],
        }

    return solve_lunar_contacts(
        0.0, sample, bodies=tuple(p for p in states if p != "Moon")
    )
