"""T1299's monthly Taibai direction table, distinct from physical Venus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_taibai.json"


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def taibai_direction_reference(lunar_day: int) -> dict[str, Any]:
    if type(lunar_day) is not int or not 1 <= lunar_day <= 30:
        raise ValueError(
            "太白月日方位表只接受实际入月日1至30，不以公历日或补配宿序代替"
        )
    record = load_source(SOURCE)
    source = record.data
    matches = [row for row in source["rows"] if lunar_day in row["lunar_days"]]
    if len(matches) != 1:
        raise ValueError("太白原文日序必须在所选主表中恰有一行")
    row = matches[0]
    witnesses = []
    for name, present, excerpt in (
        ("lower_taisho", True, row["taisho_text"]),
        (
            "ming_apparatus_reconstruction",
            row["ming_row_present"],
            row["ming_apparatus_text"],
        ),
    ):
        witnesses.append(
            {
                "witness": name,
                "status": "listed" if present else "row_deleted_in_apparatus",
                "location": row["literal_location"] if present else None,
                "horizontal_direction": (
                    row["horizontal_direction"] if present else None
                ),
                "realm": row["realm"] if present else None,
                "source_excerpt": excerpt,
                "locator": row["locator"],
                "reading_complete_for_selected_day": present,
                "applied_to_primary": name == source["selected_witness"],
            }
        )
    return {
        "ruleset_id": source["id"],
        "status": "calendar_day_reference",
        "lunar_day": lunar_day,
        "selected_witness": source["selected_witness"],
        "location": row["literal_location"],
        "horizontal_direction": row["horizontal_direction"],
        "realm": row["realm"],
        "row_id": row["row_id"],
        "row_lunar_days": row["lunar_days"],
        "witnesses": witnesses,
        "witnesses_agree_for_selected_day": row["ming_row_present"],
        "source_url": source["source_url"],
        "source_sha256": source["source_sha256"],
        "source_bundle_sha256": record.sha256,
        "locator": source["locator"],
        "title_literal": source["title_literal"],
        "table_apparatus": source["apparatus"],
        "publisher_primary": source["publisher_primary"],
        "doctrine": source["doctrine"],
        "physical_venus_position_evaluated": False,
        "astronomical_retrograde_evaluated": False,
        "movement_alignment_evaluated": False,
        "applied_to_activity_assessment": False,
        "independent_ming_edition_collated": False,
        "scope": source["scope"],
    }
