"""Finite comparison with independently observed official fixing triangles.

The source's blank glyphs cannot establish a complete fixing-state oracle.
This is separate from verification of a served reading's internal derivation.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any

from fatebridge.core.human_design_depth import line_fixings


def fixing_marker_checks(root: Path) -> dict[str, Any]:
    raw = (
        files("fatebridge.data")
        .joinpath("human_design/fixing-2026-reference.json")
        .read_bytes()
    )
    reference = json.loads(raw)
    original = {}
    for source in reference["cohort_sources"]:
        cohort_raw = (root / "tests/fixtures" / source["fixture"]).read_bytes()
        if hashlib.sha256(cohort_raw).hexdigest() != source["sha256"]:
            raise ValueError("Frozen fixing cohort changed")
        cohort = json.loads(cohort_raw)
        for case in cohort["cases"]:
            if case["id"] in original:
                raise ValueError("Duplicate fixing reference case")
            original[case["id"]] = case, cohort["planet_order"], source["sha256"]
    if len(reference["cases"]) != len(original) or len(
        {c["case_id"] for c in reference["cases"]}
    ) != len(original):
        raise ValueError("Fixing reference omitted or duplicated an original case")
    rows = []
    for observed in reference["cases"]:
        case, order, sha = original[observed["case_id"]]
        if (
            case["pdf_sha256"] != observed["pdf_sha256"]
            or sha != observed["cohort_sha256"]
        ):
            raise ValueError("Fixing observations no longer bind to the original PDF")
        sides = {
            side: [
                {
                    "body": body,
                    "gate": int(label.split(".")[0]),
                    "line": int(label.split(".")[1]),
                }
                for body, label in zip(order, case["columns"][side])
            ]
            for side in ("design", "personality")
        }
        expected_slots = {
            (side, r["body"]): r for side, items in sides.items() for r in items
        }
        if len(observed["observations"]) != 26 or {
            (r["side"], r["body"]) for r in observed["observations"]
        } != set(expected_slots):
            raise ValueError("Incomplete observed fixing slots")
        computed = {(r["side"], r["body"]): r for r in line_fixings(sides)}
        for fact in observed["observations"]:
            key = fact["side"], fact["body"]
            slot = expected_slots[key]
            if fact["gate_line"] != f"{slot['gate']}.{slot['line']}":
                raise ValueError("Observed fixing gate.line changed")
            if fact["visible_marker"] not in {
                "exaltation",
                "detriment",
                "no_visible_marker",
            }:
                raise ValueError("Unknown observed fixing glyph")
            record = computed[key]
            state = record["fixing_state"]
            projection = (
                state if state in {"exaltation", "detriment"} else "no_visible_marker"
            )
            rows.append(
                {
                    "case_id": case["id"],
                    "side": key[0],
                    "body": key[1],
                    "gate_line": fact["gate_line"],
                    "observed_marker": fact["visible_marker"],
                    "computed_rendered_projection": projection,
                    "projection_matches": projection == fact["visible_marker"],
                    "computed_fixing_state": state,
                    "source_polarity_kind": record["polarity_kind"],
                    "node_recipient": record["recipient_kind"] == "node_activation",
                    "fixing_planets": record["fixing_planets"],
                }
            )
    visible = [r for r in rows if r["observed_marker"] != "no_visible_marker"]
    return {
        "method_id": "official_visible_fixing_glyph_comparison_v1",
        "catalogue_sha256": hashlib.sha256(raw).hexdigest(),
        "case_count": len(original),
        "activation_slots_observed": len(rows),
        "visible_polarity_count": len(visible),
        "visible_polarities_matched": sum(r["projection_matches"] for r in visible),
        "visible_polarity_counts": dict(
            sorted(Counter(r["observed_marker"] for r in visible).items())
        ),
        "visible_node_recipient_count": sum(r["node_recipient"] for r in visible),
        "visible_unitary_recipient_count": sum(
            r["source_polarity_kind"] == "unitary" for r in visible
        ),
        "blank_slot_count": len(rows) - len(visible),
        "rendered_projection_matches": sum(r["projection_matches"] for r in rows),
        "mismatches": [r for r in rows if not r["projection_matches"]],
        "status": (
            "bounded_visible_marker_match"
            if all(r["projection_matches"] for r in rows)
            else "failed"
        ),
        "complete_fixing_statuses_certified": False,
        "full_384_line_meaning_acceptance": False,
        "scope": reference["scope"],
        "rendering_limit": reference["rendering_limit"],
        "cases": rows,
    }
