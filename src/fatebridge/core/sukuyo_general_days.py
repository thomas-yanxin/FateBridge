"""Complete named prose day lists, shared by classification and comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_general_day_lists.json"


def general_day_evidence(day: int) -> dict[str, Any]:
    if type(day) is not int or not 1 <= day <= 30:
        raise ValueError("一般日类入月日须为1至30的整数")
    loaded = load_source(SOURCE)
    reference = loaded.data
    classifications = []
    for witness in reference["witnesses"]:
        favorable = set(witness["favorable_lunar_days"])
        conditional = set(witness["conditional_lunar_days"])
        table = [
            {
                "lunar_day": number,
                "assessment": (
                    "favorable"
                    if number in favorable
                    else "conditional" if number in conditional else "unlisted"
                ),
            }
            for number in range(1, 31)
        ]
        witness["all_thirty_classifications"] = table
        classifications.append(
            {
                "witness": witness["witness"],
                "assessment": table[day - 1]["assessment"],
                "locator": witness["classification_locator"],
            }
        )
    reference["source_bundle_sha256"] = loaded.sha256
    return {"reference": reference, "classifications": classifications}
