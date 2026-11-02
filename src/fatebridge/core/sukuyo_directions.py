"""The lower volume's named-day travel directions, with literal variants.

Palace labels in this chapter are documentary selectors. They do not select a
person's natal palace, physical Moon, modern zodiac or geographic bearing.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional, Sequence

from fatebridge.core.sukuyo_documentary import with_text_layers
from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_travel_directions.json"
)
MANSIONS = frozenset("角亢氐房心尾箕斗女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸")


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def source_digest() -> str:
    return load_source(SOURCE).sha256


def travel_direction_evidence(
    mansion: Optional[str], candidates: Sequence[str] = ()
) -> dict[str, Any]:
    if (mansion is not None and mansion not in MANSIONS) or any(
        name not in MANSIONS for name in candidates
    ):
        raise ValueError("出行方向日宿只支持27宿（不含牛）")
    bundle = source_bundle()

    def records(name: str) -> list[dict[str, Any]]:
        return [
            {**with_text_layers(r), "source_url": bundle["source_url"]}
            for r in bundle["rules"]
            if name in r["selectors"]
        ]

    return {
        "ruleset_id": bundle["id"],
        "status": "named_day_reference" if mansion else "candidate_only",
        "mansion": mansion,
        "selected_records": records(mansion) if mansion else [],
        "candidate_records": (
            [
                {"mansion": name, "records": records(name), "applied_to_primary": False}
                for name in dict.fromkeys(candidates)
            ]
            if mansion is None
            else []
        ),
        "basis": "explicit_named_day_selectors_in_travel_chapter",
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "source_bundle_sha256": source_digest(),
        "locator": bundle["locator"],
        "selected_text": bundle["selected_text"],
        "textual_issues": deepcopy(bundle["textual_issues"]),
        "direction_inferred": False,
        "physical_palace_computed": False,
        "scope": bundle["scope"],
    }
