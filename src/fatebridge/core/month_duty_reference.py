"""Keep source durations, effective command and physical hidden roots distinct."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, Mapping

from fatebridge.core.month_duty_scan_reference import build_month_duty_scan_reference
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS

ORDER = ("year", "month", "day", "hour")


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        files("fatebridge.data")
        .joinpath("bazi_month_duty_sources_v1.json")
        .read_text(encoding="utf-8")
    )
    return value


def build_month_duty_reference(
    pillars: Mapping[str, tuple[str, str]],
) -> dict[str, Any]:
    """Observe source-named stems without selecting a day or altering roots.

    Source tables also name stems outside the conventional hidden-stem catalog.
    Those statements must not manufacture physical roots or a duty stem. Soil
    identities absent from the captured source remain unknown, not a guess.
    """
    source = _source()
    branch = pillars["month"][1]
    conventional = list(BRANCH_HIDDEN_STEMS[branch])
    layers = []
    for profile in source["profiles"]:
        month = deepcopy(profile["months"][branch])
        claims = month["claims"]
        total = sum(c["days"] for c in claims)
        for claim in claims:
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
        layers.append(
            {
                "profile_id": profile["id"],
                "source_id": source["sources"][profile["source"]]["id"],
                "source_layer": profile["layer"],
                "claim_kind": profile["claim_kind"],
                **month,
                "computed_literal_duration_sum": total,
                "equals_nominal_thirty_days": total == 30,
                "source_stems_outside_month_hidden_catalog": list(
                    dict.fromkeys(
                        c["canonical_stem"]
                        for c in claims
                        if c["canonical_stem"] is not None
                        and c["canonical_stem"] not in conventional
                    )
                ),
                "selected_duty_stem": None,
                "calendar_mapping_status": "not_adopted",
            }
        )
    annual = source["annual_literal_claim"]
    annual_total = sum(
        len(g["source_names"]) * g["each_days"] for g in annual["groups"]
    )
    return {
        "method_id": source["method_id"],
        "month_branch": branch,
        "conventional_month_hidden_stems": conventional,
        "sources": deepcopy(list(source["sources"].values())),
        "duration_source_layers": layers,
        "ditian_original_note": {
            **{
                k: deepcopy(v)
                for k, v in source["ditian_original_note"].items()
                if k not in {"months", "source"}
            },
            "source_id": source["sources"]["ditian_1947"]["id"],
            "month_ranges_as_printed": deepcopy(
                source["ditian_original_note"]["months"].get(branch)
            ),
        },
        "ditian_ren_commentary": {
            **{
                k: deepcopy(v)
                for k, v in source["ditian_ren_commentary"].items()
                if k != "source"
            },
            "source_id": source["sources"]["ditian_1947"]["id"],
        },
        "source_critique": {
            **{
                k: deepcopy(v)
                for k, v in source["sanming_critique"].items()
                if k not in {"source_text", "source"}
            },
            "source_id": source["sources"]["sanming_digital"]["id"],
        },
        "annual_duration_arithmetic": {
            "computed_literal_sum": annual_total,
            "stated_total": annual["stated_total_days"],
            "matches": annual_total == annual["stated_total_days"],
            "scope": annual["scope"],
        },
        "scanned_witness": build_month_duty_scan_reference(pillars),
        "effective_command_status": "not_adjudicated",
        "scope": source["interpretation_scope"],
        "independent_expert_review": source["independent_expert_review"],
        "calculation_effect": "none",
    }
