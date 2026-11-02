"""Audit the complete printed replacement numeric corpus without correcting it.

The forced numeric branch does not assert that a measured angle selects this
mode in either author's system. Literal agreement cannot override a malformed
source or computed plate, and does not certify the star-name labels or prose.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.fengshui.xuankong import _chart, natal_rules

MOUNTAINS = "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬"
DIRECTIONS = ("SE", "S", "SW", "E", "C", "W", "NE", "N", "NW")
ROLES = ("mountain", "facing", "period")
REFERENCE_SHA256 = "43b04b453c5ae51cb6fc6e7ebb958a6e2da58e853b254e0c69f76e1458dd0fca"
MANIFEST_SHA256 = "e08c5f9f373064f4f2c15496d296d78f1f6f71dcd4f893445372554ea342bb8c"
SOURCE_SHA256 = "b0c2a7af0a1b94f36cf1cc9f0d2ce4b65e8ea49bd793bc128b8fdc525b5ba847"


def _validate_rows(reference: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = reference["rows"]
    required = {(n, m) for n in range(1, 10) for m in MOUNTAINS}
    keys = [(r["period"], r["facing_mountain"]) for r in rows]
    if len(rows) != 216 or set(keys) != required:
        raise ValueError("All 216 distinct replacement diagrams are required")
    for index, row in enumerate(rows):
        if (
            type(row["period"]) is not int
            or row["sitting_mountain"]
            != MOUNTAINS[(MOUNTAINS.index(row["facing_mountain"]) + 12) % 24]
            or row["pdf_page"] != 511 + index
        ):
            raise ValueError("Replacement source identity or page order changed")
        if set(row["palaces"]) != set(DIRECTIONS):
            raise ValueError("All nine printed palaces are required")
        for palace in row["palaces"].values():
            if set(palace) != set(ROLES) or any(
                type(v) is not int or not 1 <= v <= 9 for v in palace.values()
            ):
                raise ValueError("All 27 explicit integer source numerals are required")
    return rows


def load_replacement_diagram_reference(folder: Path) -> dict[str, Any]:
    """Require the frozen reference, full original captures and review history."""
    raw = (folder / "reference.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Replacement reference differs from its pre-engine freeze")
    manifest_raw = (folder / "hashes.json").read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Complete replacement source manifest changed")
    manifest = json.loads(manifest_raw)
    for name, digest in manifest.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Replacement source capture or review record changed")
    reference = json.loads(raw)
    rows = _validate_rows(reference)
    if reference["source_pdf_sha256"] != SOURCE_SHA256:
        raise ValueError("Unexpected replacement source edition")
    for name, digest in reference["evidence_sha256"].items():
        # Preserve the exact historical scripts as data, without formatting or
        # executing their frozen bytes as repository Python source.
        archived = name + ".txt" if name.endswith(".py") else name
        if manifest[archived] != digest:
            raise ValueError("Pre-engine source evidence identity changed")
    frozen = json.loads((folder / "reference-freeze.json").read_text())
    if frozen["reference_sha256"] != REFERENCE_SHA256:
        raise ValueError("Source freeze must precede comparison")
    original = json.loads((folder / "native-manifest.json").read_text())["rows"]
    glyphs = json.loads((folder / "ocr-native.json").read_text())["glyphs"]
    combined = json.loads((folder / "combined-provisional.json").read_text())
    for name, field in (
        ("ocr-native.json", "native_ocr_sha256"),
        ("ocr-scale2.json", "scale2_ocr_sha256"),
    ):
        if manifest[name] != combined[field]:
            raise ValueError("Raw OCR proposal history changed")
    resolved = json.loads((folder / "unresolved-source-pixel-review.json").read_text())
    review = json.loads((folder / "source-pixel-review-completed.json").read_text())
    reviewed = [
        glyph_id
        for sheet in review["sheets"]
        if sheet["file"] != "manual-disagreements-01.png"
        for glyph_id in sheet["ids"]
    ]
    if (
        len(original) != 216
        or len(glyphs) != 5832
        or sorted(reviewed) != list(range(5832))
    ):
        raise ValueError("Every original image and distinct glyph review is required")
    for index, row in enumerate(rows):
        native = original[index]
        if (
            any(
                native[k] != row[k]
                for k in ("period", "sitting_mountain", "facing_mountain", "pdf_page")
            )
            or native["sha256"] != row["native_sha256"]
        ):
            raise ValueError("Native heading/image association changed")
        if (
            manifest[f"native-images/{row['native_image']}"] != row["native_sha256"]
            or manifest[f"grid-captures/{row['grid_capture']}"]
            != row["grid_capture_sha256"]
        ):
            raise ValueError("All 216 original source diagram captures are required")
        for j, direction in enumerate(DIRECTIONS):
            for k, role in enumerate(ROLES):
                glyph_id = index * 27 + j * 3 + k
                glyph = glyphs[glyph_id]
                proposal = combined["rows"][glyph_id]
                value = proposal["provisional_agreed"]
                if value is None:
                    value = resolved["values"][str(glyph_id)]
                if (
                    glyph["id"] != glyph_id
                    or glyph["direction"] != direction
                    or glyph["role"] != role
                    or glyph["source_image"] != row["native_image"]
                    or value != row["palaces"][direction][role]
                ):
                    raise ValueError(
                        "Printed glyph provenance or literal value changed"
                    )
    return {"reference": reference}


def _permutation_failures(
    palaces: dict[str, Any], row: dict[str, Any]
) -> list[dict[str, Any]]:
    failures = []
    for role in ROLES:
        values = [palaces[d][role] for d in DIRECTIONS]
        if any(type(v) is not int for v in values) or sorted(values) != list(
            range(1, 10)
        ):
            failures.append(
                dict(
                    period=row["period"],
                    facing_mountain=row["facing_mountain"],
                    pdf_page=row["pdf_page"],
                    role=role,
                    values=values,
                )
            )
    return failures


def audit_replacement_diagrams(data: dict[str, Any]) -> dict[str, Any]:
    rows = _validate_rows(data["reference"])
    differences = []
    source_failures = []
    engine_failures = []
    center_failures = []
    representation_failures = []
    matched_charts = 0
    checked = 0
    for index, row in enumerate(rows):
        period, facing = row["period"], row["facing_mountain"]
        source_failures.extend(_permutation_failures(row["palaces"], row))
        if row["palaces"]["C"]["period"] != period:
            center_failures.append(dict(pdf_page=row["pdf_page"], period=period))
        # A declared branch is deliberately used instead of fabricating a
        # measured offset that might select another mode in the source text.
        chart = _chart(
            period,
            (
                MOUNTAINS.index(facing),
                "replacement",
                "Forced numeric source audit; no angle applicability asserted",
            ),
        )
        actual = {
            d: {role: chart["palaces"][d][role + "_star_number"] for role in ROLES}
            for d in DIRECTIONS
        }
        engine_failures.extend(_permutation_failures(actual, row))
        for role in ROLES:
            if chart[role + "_chart"] != {d: actual[d][role] for d in DIRECTIONS}:
                representation_failures.append(
                    dict(pdf_page=row["pdf_page"], role=role)
                )
        chart_matches = True
        for j, d in enumerate(DIRECTIONS):
            for k, role in enumerate(ROLES):
                checked += 1
                printed, computed = row["palaces"][d][role], actual[d][role]
                if type(computed) is not int or printed != computed:
                    chart_matches = False
                    differences.append(
                        dict(
                            period=period,
                            sitting_mountain=row["sitting_mountain"],
                            facing_mountain=facing,
                            pdf_page=row["pdf_page"],
                            direction=d,
                            role=role,
                            printed=printed,
                            engine=computed,
                            glyph_id=index * 27 + j * 3 + k,
                        )
                    )
        matched_charts += chart_matches
    return {
        "audit_id": "shen_2011_complete_replacement_diagram_audit_v1",
        "reference_sha256": REFERENCE_SHA256,
        "source_pdf_sha256": SOURCE_SHA256,
        "source_edition": data["reference"]["source_edition"],
        "author_attribution": data["reference"]["author_attribution"],
        "engine_ruleset": natal_rules()["ruleset"],
        "numeric_mode": "forced_replacement",
        "printed_charts_checked": len(rows),
        "printed_charts_matched": matched_charts,
        "printed_numerals_checked": checked,
        "printed_numerals_matched": checked - len(differences),
        "differences": differences,
        "source_permutation_failures": source_failures,
        "source_center_label_differences": center_failures,
        "engine_permutation_failures": engine_failures,
        "engine_representation_failures": representation_failures,
        "literal_diagram_numeric_acceptance_passed": not differences,
        "complete_diagram_acceptance_passed": not any(
            (
                differences,
                source_failures,
                center_failures,
                engine_failures,
                representation_failures,
            )
        ),
        "all_216_diagrams_transcribed": True,
        "source_corrected_to_match_engine": False,
        "source_exception_allowlist_used": False,
        "independent_human_expert_review_complete": False,
        "star_name_labels_and_prose_verified": False,
        "source_angle_applicability_verified": False,
        "whole_book_conformity_established": False,
        "calendar_selection_verified": False,
        "empirical_predictive_validity_established": False,
        "authority_certified": False,
    }
