"""Separate lower-volume nature and weekday witnesses, never a source vote."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_lower_methods.json"


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def lower_methods_evidence(
    mansion: Optional[str],
    luminary: str,
    upper_nature: Optional[str],
    *,
    weekday_basis: str = "modern_utc_plus08_civil_midnight",
) -> dict[str, Any]:
    if weekday_basis not in {
        "modern_utc_plus08_civil_midnight",
        "modern_utc_plus09_civil_midnight",
    }:
        raise ValueError("未知的宿曜七曜参考日界")
    bundle = source_bundle()
    # 牛 belongs to this source table, but never to the calendar's 27 names.
    if mansion == "牛":
        raise ValueError("下卷宿性证言不能把牛宿代入历日27宿")
    group = next((g for g in bundle["nature_groups"] if mansion in g["members"]), None)
    if mansion is not None and group is None:
        raise ValueError("未知的历日27宿")
    weekday = next(
        (w for w in bundle["weekday_records"] if w["luminary"] == luminary), None
    )
    if weekday is None:
        raise ValueError("七曜只支持日月火水木金土")
    normalized_upper = "轻" if upper_nature == "轻燥" else upper_nature
    return {
        "ruleset_id": bundle["id"],
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "source_bundle_sha256": load_source(SOURCE).sha256,
        "selected_text": bundle["selected_text"],
        "nature": {
            "status": "enumerated_membership_reference" if group else "not_evaluated",
            "mansion": mansion,
            "selected_group": deepcopy(group),
            "upper_nature": upper_nature,
            "membership_differs_from_upper": (
                group["name"] != normalized_upper if group else None
            ),
            "membership_basis": bundle["membership_basis"],
            "cow_reference_not_applied_to_calendar": True,
        },
        "weekday": {
            **deepcopy(weekday),
            "basis": weekday_basis,
            "classical_daybreak_boundary_acceptance": False,
        },
        "scope": bundle["scope"],
    }
