"""Cross-chapter term identities, separate from the first month-duty witness."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, Mapping

from fatebridge.utils.data import BRANCH_HIDDEN_STEMS

ORDER = ("year", "month", "day", "hour")


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        files("fatebridge.data")
        .joinpath("bazi_month_duty_identity_v1.json")
        .read_text(encoding="utf-8")
    )
    return value


def build_month_duty_identities(
    pillars: Mapping[str, tuple[str, str]],
    duration_source_layers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Join named source terms to explicit context without selecting a duty.

    A cross-chapter identity never replaces the chapter-only transcription,
    assigns an unresolved term by analogy, or adds a physical hidden stem.
    """
    result = deepcopy(_source())
    identities = {r["source_name"]: r for r in result["identity_claims"]}
    observations = []
    for layer in duration_source_layers:
        for rank, claim in enumerate(layer["claims"]):
            identity = identities.get(claim["source_name"])
            if identity is None:
                continue
            stem = identity["canonical_stem"]
            observations.append(
                {
                    "profile_id": layer["profile_id"],
                    "claim_rank": rank,
                    "source_name": claim["source_name"],
                    "literal_days": claim["days"],
                    "month_claim_original_pdf_pages": deepcopy(
                        layer["original_pdf_pages"]
                    ),
                    "chapter_only_canonical_stem": claim["canonical_stem"],
                    "identity_claim_id": identity["id"],
                    "cross_chapter_canonical_stem": stem,
                    "identity_status": identity["identity_status"],
                    "visible_positions": (
                        [p for p in ORDER if pillars[p][0] == stem] if stem else None
                    ),
                    "hidden_positions": (
                        [
                            {"pillar": p, "branch": pillars[p][1], "hidden_rank": i}
                            for p in ORDER
                            for i, hidden in enumerate(
                                BRANCH_HIDDEN_STEMS[pillars[p][1]]
                            )
                            if hidden == stem
                        ]
                        if stem
                        else None
                    ),
                    "effective_command_status": "not_adjudicated",
                }
            )
    result["month_branch"] = pillars["month"][1]
    result["month_term_observations"] = observations
    return result
