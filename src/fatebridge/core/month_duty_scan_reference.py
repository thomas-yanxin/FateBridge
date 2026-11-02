"""A named scanned witness, separate from the preserved digital transcription."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, Mapping

from fatebridge.core.month_duty_identity import build_month_duty_identities
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS

ORDER = ("year", "month", "day", "hour")


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        files("fatebridge.data")
        .joinpath("bazi_month_duty_scan_v1.json")
        .read_text(encoding="utf-8")
    )
    return value


def build_month_duty_scan_reference(
    pillars: Mapping[str, tuple[str, str]],
) -> dict[str, Any]:
    """Deliver source readings and actual occurrences without a duty calendar.

    No table duration, corrected character or source total can manufacture a
    hidden stem, alter a root budget or decide which source is effective.
    """
    source = _source()
    branch = pillars["month"][1]
    conventional = BRANCH_HIDDEN_STEMS[branch]
    layers = []
    for profile in source["profiles"]:
        month = deepcopy(profile["months"][branch])
        for claim in month["claims"]:
            stem = claim["canonical_stem"]
            claim["visible_positions"] = (
                [p for p in ORDER if pillars[p][0] == stem] if stem else None
            )
            claim["hidden_positions"] = (
                [
                    {"pillar": p, "branch": pillars[p][1], "hidden_rank": rank}
                    for p in ORDER
                    for rank, hidden in enumerate(BRANCH_HIDDEN_STEMS[pillars[p][1]])
                    if hidden == stem
                ]
                if stem
                else None
            )
        total = sum(claim["days"] for claim in month["claims"])
        layers.append(
            {
                "profile_id": profile["id"],
                "source_layer": profile["source_layer"],
                "claim_kind": profile["claim_kind"],
                **month,
                "computed_literal_duration_sum": total,
                "equals_nominal_thirty_days": total == 30,
                "source_stems_outside_month_hidden_catalog": list(
                    dict.fromkeys(
                        c["canonical_stem"]
                        for c in month["claims"]
                        if c["canonical_stem"] is not None
                        and c["canonical_stem"] not in conventional
                    )
                ),
                "selected_duty_stem": None,
                "calendar_mapping_status": "not_adopted",
            }
        )
    annual = deepcopy(source["annual_literal_claim"])
    total = sum(len(g["source_names"]) * g["each_days"] for g in annual["groups"])
    annual.update(
        computed_literal_sum=total,
        matches_stated_total=total == annual["stated_total_days"],
        scope="所列书影的字面算术；不是实际历月长度、原书应如何改字或有效力量裁定。",
    )
    return {
        "method_id": source["method_id"],
        "source": deepcopy(source["source"]),
        "month_branch": branch,
        "duration_source_layers": layers,
        "annual_duration_arithmetic": annual,
        "closing_critique": deepcopy(source["closing_critique"]),
        "source_comparison_scope": source["source_comparison_scope"],
        "independent_expert_review": source["independent_expert_review"],
        "calendar_mapping_status": "not_adopted",
        "selected_duty_stem": None,
        "effective_command_status": "not_adjudicated",
        "calculation_effect": "none",
        "cross_chapter_identities": build_month_duty_identities(pillars, layers),
    }
