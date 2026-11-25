"""Independent interval controls for the instantaneous C04 clock."""

from fractions import Fraction
from pathlib import Path

from tests.support.reference_data import read, sha

_PATH = (
    Path(__file__).parents[1]
    / "data/astro/iers_c04/modern-clock-regressions-v1.json.gz"
)
assert sha(_PATH) == "9ff8f17a72334d0372acd6302222086c95118b697dcc54aa96e744b10bd50ed6"
CLOCK = read(_PATH)
SCALAR_GATE = float(CLOCK["scalar_compatibility_gate_seconds"])


def assert_clock_point(days: Fraction, expected: dict[str, str]) -> None:
    error = max(abs(days - Fraction(expected[key])) for key in ("lower", "upper"))
    assert error * 86400 <= Fraction(CLOCK["gate_seconds"])
    assert float(days).hex() == expected["RN_hex"]
