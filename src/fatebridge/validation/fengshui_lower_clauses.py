"""Collate a complete printed clause set without resolving conflicts by fiat.

The three diagrams are separately transcribed source pixels. Matching their
81 numerals cannot certify the other 213 diagrams, an entire book or outcomes.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.core.fengshui.xuankong import xuankong_natal

MOUNTAINS = "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬"
FIELDS = ("mountain_seed", "facing_seed", "mountain_flight", "facing_flight")
DIRECTIONS = {"C", "N", "NE", "E", "SE", "S", "SW", "W", "NW"}
SOURCE_SHA256 = "b0c2a7af0a1b94f36cf1cc9f0d2ce4b65e8ea49bd793bc128b8fdc525b5ba847"
DIAGRAM_KEYS = {(4, "酉"), (1, "卯"), (6, "乾")}
REFERENCE_SHA256 = "85a10d759544d5b7729e6ffbec6427a1a5ee443b353184d0daa49e34f3b5ac88"


def _literal_values(literal: str) -> dict[str, Any]:
    digits = "一二三四五六七八九"
    common = re.fullmatch(
        rf"[{digits}]运挨星[，,。]?([{digits}])(?:天星)?到山[，,。]?"
        rf"([{digits}])(?:天星)?到向[，,。]?飞星(山向均[顺逆]|山[顺逆]向[顺逆])",
        literal,
    )
    split = re.fullmatch(
        rf"[{digits}]运挨星，([{digits}])到山，([顺逆])行，(?:犯下水，)?"
        rf"([{digits}])到向，([顺逆])行",
        literal,
    )
    if common:
        mountain, facing, flight = common.groups()
        if flight.startswith("山向均"):
            mountain_flight = facing_flight = flight[-1]
        else:
            mountain_flight, facing_flight = flight[1], flight[3]
    elif split:
        mountain, mountain_flight, facing, facing_flight = split.groups()
    else:
        raise ValueError("Unparsed printed clause cannot receive numeric acceptance")
    return {
        "mountain_seed": digits.index(mountain) + 1,
        "facing_seed": digits.index(facing) + 1,
        "mountain_flight": "forward" if mountain_flight == "顺" else "reverse",
        "facing_flight": "forward" if facing_flight == "顺" else "reverse",
    }


def _rows(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    keys = [(r["period"], r["facing_mountain"]) for r in rows]
    if len(keys) != 216 or set(keys) != {
        (p, mountain) for p in range(1, 10) for mountain in MOUNTAINS
    }:
        raise ValueError(
            "All 216 distinct printed mountain-period clauses are required"
        )
    for row in rows:
        if (
            type(row["period"]) is not int
            or row["sitting_mountain"]
            != MOUNTAINS[(MOUNTAINS.index(row["facing_mountain"]) + 12) % 24]
        ):
            raise ValueError("Invalid period or nonopposite printed mountains")
        for role in ("mountain", "facing"):
            seed = row[f"{role}_seed"]
            if type(seed) is not int or not 1 <= seed <= 9:
                raise ValueError("Invalid printed seed")
            if row[f"{role}_flight"] not in {"forward", "reverse"}:
                raise ValueError("Unknown printed flight")
    return dict(zip(keys, rows))


def load_lower_clause_reference(folder: Path) -> dict[str, Any]:
    """Require every frozen crop and both kinds of conflicting source evidence."""
    raw_reference = (folder / "reference.json").read_bytes()
    if hashlib.sha256(raw_reference).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Printed clause reference differs from its pre-engine freeze")
    reference = json.loads(raw_reference)
    if not isinstance(reference, dict):
        raise ValueError("Printed clause reference must be an object")
    _rows(reference["rows"])
    if reference["protocol"]["source"]["pdf_sha256"] != SOURCE_SHA256:
        raise ValueError("Unexpected primary edition")
    expected = {
        "reference.json",
        "protocol.json",
        "diagram-checks.json",
        "ocr-checks.json",
        "ocr-manual-review.json",
        "edition-notes.json",
        "modern-page-005.png",
        "modern-page-006.png",
        "modern-page-009.png",
        "modern-page-302.png",
        "modern-page-307.png",
        "modern-page-324.png",
    }
    capture_files = set()
    for row in reference["rows"]:
        name = (
            f"p{row['pdf_page']:03d}-{row['sitting_mountain']}-"
            f"{row['facing_mountain']}-{row['period']}.png"
        )
        if row["capture"]["file"] != name:
            raise ValueError("Unexpected source capture path")
        capture_files.add(f"captures/{name}")
    if len(capture_files) != 216:
        raise ValueError("All 216 distinct clause captures are required")
    expected |= capture_files
    manifest = json.loads((folder / "hashes.json").read_text())
    if set(manifest) != expected:
        raise ValueError("Incomplete printed clause capture manifest")
    for name, digest in manifest.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Printed clause source capture changed")
    if (
        hashlib.sha256((folder / "protocol.json").read_bytes()).hexdigest()
        != reference["protocol_sha256"]
    ):
        raise ValueError("Printed clause protocol changed")
    for row in reference["rows"]:
        if manifest[f"captures/{row['capture']['file']}"] != row["capture"]["sha256"]:
            raise ValueError("Clause capture metadata does not match its pixels")
    diagrams = json.loads((folder / "diagram-checks.json").read_text())
    if diagrams["source_pdf_sha256"] != SOURCE_SHA256:
        raise ValueError("Diagrams must come from the same printed edition")
    for diagram in diagrams["cases"]:
        if manifest.get(diagram["image"]) != diagram["image_sha256"]:
            raise ValueError("Same-edition diagram image changed")
    edition = json.loads((folder / "edition-notes.json").read_text())
    if edition["source_pdf_sha256"] != SOURCE_SHA256:
        raise ValueError("Edition notes must identify the same primary file")
    return {"reference": reference, "diagrams": diagrams, "edition_notes": edition}


def _diagram_trace(palaces: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for role in ("mountain", "facing"):
        center, northwest = palaces["C"][role], palaces["NW"][role]
        result[f"{role}_seed"] = center
        if northwest == center % 9 + 1:
            flight = "forward"
        elif northwest == (center - 2) % 9 + 1:
            flight = "reverse"
        else:
            raise ValueError("Printed center/NW does not identify a one-step flight")
        result[f"{role}_flight"] = flight
    return result


def audit_lower_clauses(
    data: dict[str, Any], web_reference: dict[str, Any]
) -> dict[str, Any]:
    printed = _rows(data["reference"]["rows"])
    web = _rows(web_reference["shen_cases"])
    diagrams = data["diagrams"]["cases"]
    diagram_keys = [(r["period"], r["facing_mountain"]) for r in diagrams]
    if len(diagram_keys) != 3 or set(diagram_keys) != DIAGRAM_KEYS:
        raise ValueError(
            "All three independently captured conflicting diagrams are required"
        )
    charts = {}
    prose_differences = []
    web_differences = []
    for key, row in printed.items():
        if "一二三四五六七八九".index(row["literal_prefix"][0]) + 1 != key[0]:
            raise ValueError("Printed period must match its literal clause")
        if _literal_values(row["literal_prefix"]) != {
            field: row[field] for field in FIELDS
        }:
            raise ValueError(
                "Numeric metadata must preserve the uncorrected literal clause"
            )
        request = XuankongRequest.model_validate(
            {
                "house": {
                    "facing_degrees": MOUNTAINS.index(key[1]) * 15,
                    "north_reference": "magnetic",
                },
                "period": {
                    "basis": "expert_confirmed",
                    "period_number": key[0],
                    "evidence": "Synthetic fixed-period source comparison, not a real house",
                },
            }
        )
        chart = xuankong_natal(request)["chart"]
        charts[key] = chart
        expected = {field: row[field] for field in FIELDS}
        actual = {
            f"{role}_{field}": chart["trace"][role][
                "seed_star_number" if field == "seed" else "flight"
            ]
            for role in ("mountain", "facing")
            for field in ("seed", "flight")
        }
        if actual != expected:
            prose_differences.append(
                dict(
                    period=key[0],
                    sitting_mountain=row["sitting_mountain"],
                    facing_mountain=key[1],
                    pdf_page=row["pdf_page"],
                    literal_prefix=row["literal_prefix"],
                    printed=expected,
                    engine=actual,
                )
            )
        web_expected = {field: web[key][field] for field in FIELDS}
        if expected != web_expected:
            web_differences.append(
                dict(
                    period=key[0],
                    facing_mountain=key[1],
                    printed=expected,
                    web=web_expected,
                )
            )
    cell_differences = []
    internal_conflicts = []
    cells_checked = 0
    for diagram in diagrams:
        key = (diagram["period"], diagram["facing_mountain"])
        row = printed[key]
        if (
            diagram["sitting_mountain"] != row["sitting_mountain"]
            or diagram["pdf_page"] != row["pdf_page"]
        ):
            raise ValueError("Diagram and prose must identify the same printed chart")
        palaces = diagram["palaces"]
        if set(palaces) != DIRECTIONS:
            raise ValueError("All nine printed diagram palaces are required")
        for direction, values in palaces.items():
            if set(values) != {"mountain", "facing", "period"} or any(
                type(value) is not int or not 1 <= value <= 9
                for value in values.values()
            ):
                raise ValueError("All 27 printed star numerals are required")
            for role, value in values.items():
                actual = charts[key]["palaces"][direction][f"{role}_star_number"]
                cells_checked += 1
                if actual != value:
                    cell_differences.append(
                        dict(
                            period=key[0],
                            facing_mountain=key[1],
                            direction=direction,
                            role=role,
                            printed=value,
                            engine=actual,
                        )
                    )
        trace = _diagram_trace(palaces)
        prose = {field: row[field] for field in FIELDS}
        if trace != prose:
            internal_conflicts.append(
                dict(
                    period=key[0],
                    sitting_mountain=row["sitting_mountain"],
                    facing_mountain=key[1],
                    pdf_page=row["pdf_page"],
                    literal_prefix=row["literal_prefix"],
                    printed_prose=prose,
                    printed_diagram=trace,
                )
            )
    return {
        "audit_id": "shen_2011_full_lower_clause_collation_v1",
        "source_pdf_sha256": SOURCE_SHA256,
        "source_edition": data["reference"]["protocol"]["source"]["edition"],
        "edition_notes": data["edition_notes"],
        "printed_prose_checked": len(printed),
        "printed_prose_matched": len(printed) - len(prose_differences),
        "printed_prose_differences": prose_differences,
        "web_numeric_pairs_checked": len(web),
        "web_numeric_pairs_matched": len(web) - len(web_differences),
        "web_numeric_differences": web_differences,
        "same_edition_diagrams_checked": len(diagrams),
        "diagram_numerals_checked": cells_checked,
        "diagram_numeral_differences": cell_differences,
        "diagram_spot_checks_passed": not cell_differences,
        "same_edition_prose_diagram_conflicts": internal_conflicts,
        "unresolved_source_conflict_count": len(internal_conflicts),
        "complete_printed_clause_acceptance_passed": not prose_differences
        and not internal_conflicts,
        "silent_correction_or_edition_switch_authorized": False,
        "all_216_diagrams_collated": False,
        "whole_book_conformity_established": False,
        "independent_human_expert_review_complete": False,
        "calendar_selection_verified": False,
        "empirical_predictive_validity_established": False,
        "authority_certified": False,
    }
