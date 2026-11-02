"""T1299 clothing witnesses and declared-action conditions.

The operational list, its complement, and literal forecast verses are separate
source statements. Ming apparatus does not supply a negative complement or
license silently replacing its non-mansion character 并 with 井.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_clothing.json"


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def clothing_reference(calendar: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.sukuyo_relations import normalize_mansion

    record = load_source(SOURCE)
    source = record.data
    mansion = calendar.get("natal_su27")
    if mansion is not None and (not isinstance(mansion, str) or len(mansion) != 1):
        raise ValueError("衣事章须使用已核定的二十七宿，不含牛或并字")
    candidates = [mansion] if mansion else calendar.get("candidate_su27s", [])
    names = []
    rows = []
    for value in candidates:
        if not isinstance(value, str) or len(value) != 1:
            raise ValueError("衣事章须使用已核定的二十七宿，不含牛或并字")
        name = normalize_mansion(value)
        matches = [r for r in source["verse_rows"] if r["mansion"] == name]
        if len(matches) != 1 or name in names:
            raise ValueError("衣事章须使用不重复的二十七宿，不含牛或并字")
        names.append(name)
        primary = (
            "favorable" if name in source["primary_positive_mansions"] else "caution"
        )
        ming_listed = name in source["ming_recognized_positive_mansions"]
        rows.append(
            {
                "mansion": name,
                "verse": matches[0],
                "upper_literal_cutting_statement": next(
                    (
                        r
                        for r in source["upper_literal_cutting_statements"]
                        if r["mansion"] == name
                    ),
                    None,
                ),
                "primary_assessment": primary,
                "comparisons": [
                    {
                        "witness": "lower_taisho",
                        "membership": (
                            "listed"
                            if primary == "favorable"
                            else "explicit_complement"
                        ),
                        "assessment": primary,
                        "source_excerpt": source["summary_taisho"],
                        "applied_to_primary": True,
                    },
                    {
                        "witness": "ming_apparatus_reconstruction",
                        "membership": (
                            "listed"
                            if ming_listed
                            else "not_recognized_in_selected_list"
                        ),
                        "assessment": "favorable" if ming_listed else None,
                        "source_excerpt": source["summary_ming_apparatus"],
                        "applied_to_primary": False,
                        "unlisted_complement_assessment": None,
                    },
                ],
            }
        )
    complete = bool(mansion) or bool(
        calendar.get("profile_calculation", {}).get(
            "candidate_set_complete_under_declared_reconstructions"
        )
    )
    assessments = {row["primary_assessment"] for row in rows}
    primary_assessment = (
        next(iter(assessments)) if complete and rows and len(assessments) == 1 else None
    )
    return {
        "ruleset_id": source["id"],
        "status": (
            "mansion_reference"
            if mansion
            else (
                "candidate_common_membership"
                if primary_assessment
                else "mansion_unresolved"
            )
        ),
        "mansion": names[0] if mansion else None,
        "candidate_mansions": names if not mansion else [],
        "candidate_set_complete_under_declared_profile": complete,
        "primary_assessment": primary_assessment,
        "selected_witness": source["selected_witness"],
        "candidate_references": rows,
        "primary_positive_mansions": source["primary_positive_mansions"],
        "ming_literal_list": source["ming_literal_list"],
        "ming_unresolved_tokens": source["ming_unresolved_tokens"],
        "ming_unlisted_complement_assessment": None,
        "verse_and_literal_forecasts_applied_to_aggregate": False,
        "independent_ming_edition_collated": False,
        "historical_clock_mapping_evaluated": False,
        "real_world_event_prediction_evaluated": False,
        "source_url": source["source_url"],
        "source_sha256": source["source_sha256"],
        "source_bundle_sha256": record.sha256,
        "locator": source["locator"],
        "unmapped_clothing_predicates": source["unmapped_clothing_predicates"],
        "scope": source["scope"],
    }
