"""Archived worked-example inputs for Heluo calculation tests."""

import json
from pathlib import Path
from typing import Any, Literal

from fatebridge.core.heluo.heluo import calculate

ROOT = Path(__file__).parents[2] / "fixtures/numerology_nlc_v1"
REFERENCE = json.loads((ROOT / "worked-reference.json").read_text())


def calculate_case(
    case: dict[str, Any], *, month_yang_ling: bool | Literal["source"] | None = "source"
) -> dict[str, Any]:
    pillars = dict(zip(("year", "month", "day", "hour"), case["pillars"]))
    return calculate(
        four_pillars=pillars,
        gender=case["gender"],
        birth_year=case["computational_year"],
        month_zhi=pillars["month"][1],
        hour_zhi=pillars["hour"][1],
        month_yang_ling=(
            case["yang_ling"] if month_yang_ling == "source" else month_yang_ling
        ),
    )
