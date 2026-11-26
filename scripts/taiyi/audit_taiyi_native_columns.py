"""Audit frozen native-facsimile semantic readings, never generate expectations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from scripts.taiyi.taiyi_native_sources import CORPUS as CORPUS
from scripts.taiyi.taiyi_native_sources import CORRECTION_SHA, MANIFEST_SHA
from scripts.taiyi.taiyi_native_sources import source_readings as source_readings


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    data = source_readings(corpus)

    comparisons: dict[str, list[dict[str, Any]]] = {
        "positions": [],
        "counts": [],
        "printed_generals": [],
    }
    missing_generals = []
    for row in data["rows"]:
        actual = cyclic_core(row["ju"], yin=row["yin"])
        for group, values in (
            ("positions", row["positions"]),
            ("counts", row["table_counts"]),
            ("printed_generals", row["printed_generals"]),
        ):
            for field, expected in values.items():
                item = {
                    "id": row["id"],
                    "field": field,
                    "page": row["page"],
                    "columns_from_right": row["columns_from_right"],
                }
                if expected is None:
                    missing_generals.append(item)
                else:
                    comparisons[group].append(
                        {
                            **item,
                            "source_value": expected,
                            "actual_value": actual[field],
                            "matches": expected == actual[field],
                        }
                    )
    return {
        "id": "jinjing_native_144_semantic_columns_v1",
        "version": "1.0.0",
        "author": "FateBridge contributors",
        "source_manifest_sha256": MANIFEST_SHA,
        "correction_manifest_sha256": CORRECTION_SHA,
        "required_rows": 144,
        "selected_semantic_observations": 864,
        "groups": {
            key: {
                "observations": len(items),
                "matching": sum(i["matches"] for i in items),
                "differences": [i for i in items if not i["matches"]],
            }
            for key, items in comparisons.items()
        },
        "unprinted_general_slots": missing_generals,
        "general_values_inferred_from_counts": False,
        "initial_manual_corrections": data["corrections"]["entries"],
        "source_rows": data["rows"],
        "glyph_adjudication_claimed": False,
        "independent_human_expert_reviewed": False,
        "blinded_reading": False,
        "source_scope": data["manifest"]["scope"],
        "new_dated_cases": 0,
        "classical_acceptance_passed": False,
        "full_ancient_calendar_reconstructed": False,
        "real_world_efficacy": "not_tested",
    }
