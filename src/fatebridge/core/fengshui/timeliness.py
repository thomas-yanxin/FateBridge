"""Wang Tingzhi's basic period phases, kept separate from site judgments."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, cast

from .mutual_geometry import describe_mutual_geometry, geometry_provenance


@lru_cache(maxsize=1)
def _data() -> Dict[str, Any]:
    path = Path(__file__).parents[2] / "data/fengshui/wang-timeliness-v1.json"
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def timeliness_provenance() -> Dict[str, Any]:
    data = _data()
    return {
        **deepcopy(data["ruleset"]),
        "sources": [deepcopy(data["source"])],
        "geometry_provenance": geometry_provenance(),
    }


def classify_timeliness(number: int, current: Optional[int]) -> Dict[str, Any]:
    """Classify an actual star, never a palace number or an inferred period.

    The cyclic rule implements the printed nine-column table. The separate
    mutual-use table is an exception reference, not a change to basic phase or
    permission to apply the existing current-star external-form rule.
    """
    if type(number) is not int or number not in range(1, 10):
        raise ValueError("star number must be an integer from 1 through 9")
    if current is not None and (
        type(current) is not int or current not in range(1, 10)
    ):
        raise ValueError("current period must be an integer from 1 through 9")
    offset = None if current is None else (number - current) % 9
    phase = (
        "unknown"
        if offset is None
        else (
            "prosperous"
            if offset == 0
            else (
                "growing"
                if offset in (1, 2)
                else "declining" if offset in (7, 8) else "dormant"
            )
        )
    )
    members = [] if current is None else _data()["mutual_use_numbers"][str(current)]
    return {
        "rule_id": "wang_zhongzhou_timeliness_v1.basic_phase",
        "source_ids": ["WZT1"],
        "phase": phase,
        "traditional_label": _data()["phase_labels"][phase],
        "star_number": number,
        "current_period_number": current,
        "forward_cycle_offset": offset,
        "evidence": {
            "star_number": number,
            "explicit_current_period_number": current,
        },
        "mutual_use_reference": {
            "rule_id": "wang_zhongzhou_timeliness_v1.mutual_use_numbers",
            "source_ids": ["WZT1"],
            "period_numbers": deepcopy(members),
            "numeric_membership": None if current is None else number in members,
            "application_status": "numeric_reference_only_no_site_verdict",
            "geometry": describe_mutual_geometry(number, current),
        },
        "verdict_scope": "author_basic_phase_not_site_quality_fortune_or_action_permission",
        "external_form_policy": "does_not_extend_current_star_presence_rule",
    }
