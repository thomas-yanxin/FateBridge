"""Compare every star in a fixed printed lower-chart corpus, preserving errors.

A literal-matching implementation must still obey a nine-star permutation.
Neither a source exception nor a more agreeable edition can clear this gate.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.core.fengshui.xuankong import xuankong_natal

MOUNTAINS = "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬"
DIRECTIONS = ("SE", "S", "SW", "E", "C", "W", "NE", "N", "NW")
ROLES = ("mountain", "facing", "period")
REFERENCE_SHA256 = "44488715143b6e6aebcfe8ae638397ced12ed07dfee392cce81440a43c8de483"
SOURCE_SHA256 = "b0c2a7af0a1b94f36cf1cc9f0d2ce4b65e8ea49bd793bc128b8fdc525b5ba847"


def _validate_rows(reference: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = reference["rows"]
    keys = [(row["period"], row["facing_mountain"]) for row in rows]
    required = {(period, mountain) for period in range(1, 10) for mountain in MOUNTAINS}
    if len(keys) != 216 or set(keys) != required:
        raise ValueError("All 216 distinct printed diagram pairs are required")
    for row in rows:
        if (
            type(row["period"]) is not int
            or row["sitting_mountain"]
            != MOUNTAINS[(MOUNTAINS.index(row["facing_mountain"]) + 12) % 24]
        ):
            raise ValueError("Invalid source period or opposite mountains")
        if set(row["palaces"]) != set(DIRECTIONS):
            raise ValueError("All nine diagram palaces are required")
        for palace in row["palaces"].values():
            if set(palace) != set(ROLES) or any(
                type(value) is not int or not 1 <= value <= 9
                for value in palace.values()
            ):
                raise ValueError("All 27 explicit integer source numerals are required")
    return rows


def load_lower_diagram_reference(folder: Path) -> dict[str, Any]:
    raw = (folder / "reference.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Diagram reference differs from its pre-engine freeze")
    reference = json.loads(raw)
    rows = _validate_rows(reference)
    if reference["source_pdf_sha256"] != SOURCE_SHA256:
        raise ValueError("Unexpected source edition")
    expected = {
        "reference.json",
        "protocol.json",
        "source-freeze.json",
        "manual-review-01.json",
        "manual-review-02.json",
        "manual-review-03.json",
        "candidate-visual-review.json",
        "source-internal-consistency.json",
        "modern-page-353.png",
        "historical-page-57.png",
        "native-image-manifest.json",
        "anomaly-pixel-review.json",
    }
    for row in rows:
        name = f"{row['sitting_mountain']}-{row['facing_mountain']}-{row['period']}.png"
        if row["native_image"] != name:
            raise ValueError("Unexpected native diagram path")
        expected.add(f"native-images/{name}")
    manifest = json.loads((folder / "hashes.json").read_text())
    if set(manifest) != expected:
        raise ValueError("Incomplete full diagram source manifest")
    for name, digest in manifest.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Full diagram source capture changed")
    if manifest["protocol.json"] != reference["protocol_sha256"]:
        raise ValueError("Diagram protocol identity changed")
    if manifest["native-image-manifest.json"] != reference["native_manifest_sha256"]:
        raise ValueError("Native image association manifest changed")
    frozen = json.loads((folder / "source-freeze.json").read_text())
    if frozen["reference_sha256"] != REFERENCE_SHA256:
        raise ValueError("Source freeze must precede comparison")
    associations = json.loads((folder / "native-image-manifest.json").read_text())
    associated = {
        (row["period"], row["facing_mountain"]): row for row in associations["rows"]
    }
    if len(associations["rows"]) != 216 or set(associated) != {
        (row["period"], row["facing_mountain"]) for row in rows
    }:
        raise ValueError("All 216 native image associations are required")
    glyph_ids = []
    for row in rows:
        if (
            manifest[f"native-images/{row['native_image']}"]
            != row["native_image_sha256"]
        ):
            raise ValueError("Numeric source must identify its original image")
        original = associated[(row["period"], row["facing_mountain"])]
        if (
            original["diagram"] != row["source_diagram"]
            or original["sha256"] != row["native_image_sha256"]
        ):
            raise ValueError("Source image association was changed")
        for direction in DIRECTIONS:
            for role in ROLES:
                glyph_ids.append(row["provenance"][direction][role]["glyph_id"])
    if sorted(glyph_ids) != list(range(5832)):
        raise ValueError("Every printed glyph must retain distinct provenance")
    return {
        "reference": reference,
        "anomaly_pixel_review": json.loads(
            (folder / "anomaly-pixel-review.json").read_text()
        ),
    }


def _permutation_failures(
    palaces: dict[str, Any], period: int, facing: str
) -> list[dict[str, Any]]:
    failures = []
    for role in ROLES:
        values = [palaces[direction][role] for direction in DIRECTIONS]
        if sorted(values) != list(range(1, 10)):
            failures.append(
                dict(period=period, facing_mountain=facing, role=role, values=values)
            )
    return failures


def audit_lower_diagrams(data: dict[str, Any]) -> dict[str, Any]:
    rows = _validate_rows(data["reference"])
    differences = []
    source_invariants = []
    engine_invariants = []
    center_label_differences = []
    matched_charts = 0
    checked = 0
    for row in rows:
        period, facing = row["period"], row["facing_mountain"]
        source_invariants.extend(_permutation_failures(row["palaces"], period, facing))
        if row["palaces"]["C"]["period"] != period:
            center_label_differences.append(
                dict(
                    period=period,
                    facing_mountain=facing,
                    printed_center=row["palaces"]["C"]["period"],
                )
            )
        request = XuankongRequest.model_validate(
            {
                "house": {
                    "facing_degrees": MOUNTAINS.index(facing) * 15,
                    "north_reference": "magnetic",
                },
                "period": {
                    "basis": "expert_confirmed",
                    "period_number": period,
                    "evidence": "Synthetic confirmed period for literal source audit; not a real site",
                },
            }
        )
        chart = xuankong_natal(request)["chart"]
        actual = {
            direction: {
                role: chart["palaces"][direction][f"{role}_star_number"]
                for role in ROLES
            }
            for direction in DIRECTIONS
        }
        engine_invariants.extend(_permutation_failures(actual, period, facing))
        chart_matches = True
        for direction in DIRECTIONS:
            for role in ROLES:
                checked += 1
                expected, value = (
                    row["palaces"][direction][role],
                    actual[direction][role],
                )
                if expected != value:
                    chart_matches = False
                    differences.append(
                        dict(
                            period=period,
                            sitting_mountain=row["sitting_mountain"],
                            facing_mountain=facing,
                            pdf_page=row["source_diagram"]["page"],
                            direction=direction,
                            role=role,
                            printed=expected,
                            engine=value,
                            glyph_id=row["provenance"][direction][role]["glyph_id"],
                        )
                    )
        matched_charts += chart_matches
    return {
        "audit_id": "shen_2011_complete_lower_diagram_audit_v1",
        "source_pdf_sha256": SOURCE_SHA256,
        "reference_sha256": REFERENCE_SHA256,
        "printed_charts_checked": len(rows),
        "printed_charts_matched": matched_charts,
        "printed_numerals_checked": checked,
        "printed_numerals_matched": checked - len(differences),
        "differences": differences,
        "literal_diagram_numeric_acceptance_passed": not differences,
        "source_permutation_failures": source_invariants,
        "source_center_label_differences": center_label_differences,
        "engine_permutation_failures": engine_invariants,
        "complete_diagram_acceptance_passed": not any(
            (
                differences,
                source_invariants,
                center_label_differences,
                engine_invariants,
            )
        ),
        "anomaly_pixel_review": data["anomaly_pixel_review"],
        "all_216_diagrams_transcribed": True,
        "source_corrected_to_match_engine": False,
        "source_exception_allowlist_used": False,
        "independent_human_expert_review_complete": False,
        "whole_book_conformity_established": False,
        "calendar_selection_verified": False,
        "empirical_predictive_validity_established": False,
        "authority_certified": False,
    }
