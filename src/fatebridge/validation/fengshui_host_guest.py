"""Source definitions, all 81 element pairs, and all 432 literal axis slots."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from fatebridge.core.fengshui.host_guest import analyze, classify, validate
from fatebridge.core.fengshui.xuankong import _bundle, _chart

REFERENCE_SHA256 = "4065bc975e47bfd583d302addfb55238177c2bce8a2546671abc73b3c54049a6"
MANIFEST_SHA256 = "fb64c29bdeda3259ae5f689d5c952c62bf31a265387b3e9efaf7c092fdb74a19"


def load_host_guest_reference(folder: Path) -> dict[str, Any]:
    raw = (folder / "hashes.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Retain the before-implementation source manifest")
    manifest = json.loads(raw)
    if len(manifest) != 224 or manifest.get("reference.json") != REFERENCE_SHA256:
        raise ValueError("Retain every original clause and definition capture")
    for name, digest in manifest.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Source capture changed")
    return cast(dict[str, Any], json.loads((folder / "reference.json").read_text()))


def audit_host_guest_reference(reference: dict[str, Any]) -> dict[str, Any]:
    required = {
        (p, n)
        for p in range(1, 10)
        for n in "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬"
    }
    rows = reference["full_lower_clauses"]
    if (
        len(rows) != 216
        or {(r["period"], r["facing_mountain"]) for r in rows} != required
    ):
        raise ValueError("All 216 lower clauses are required, including ambiguous ones")
    elements = reference["star_elements"]
    matrix = reference["derived_host_guest_matrix"]
    pair_differences = []
    for host in range(1, 10):
        for guest in range(1, 10):
            actual = classify(host, guest)["label"]
            expected = matrix[elements[str(host)]][elements[str(guest)]]
            if actual != expected:
                pair_differences.append(
                    dict(host=host, guest=guest, expected=expected, actual=actual)
                )
    terms = []
    mountains = _bundle()["mountains"]
    for row in rows:
        index = next(
            i for i, m in enumerate(mountains) if m["name"] == row["facing_mountain"]
        )
        chart = _chart(
            row["period"],
            (index, "lower", "declared source audit; not angle certification"),
        )
        analysis = analyze({"candidates": [chart]})
        validate({"host_guest_analysis": analysis}, {"candidates": [chart]})
        for axis, key in (("sitting", "山"), ("facing", "向")):
            value = analysis["candidates"][0]["axes"][axis]
            record = value["relations"][-1]
            labels = row["labels"][key]
            terms.append(
                {
                    "period": row["period"],
                    "sitting_mountain": row["sitting_mountain"],
                    "facing_mountain": row["facing_mountain"],
                    "axis": axis,
                    "direction": value["direction"],
                    "printed_labels": labels,
                    "computed_label": record["label"],
                    "host": record["host"],
                    "guest": record["guest"],
                    "matched": (
                        record["label"] == labels[0] if len(labels) == 1 else None
                    ),
                    "source_page": row["page"],
                    "literal_full_clause": row["literal_full_clause"],
                }
            )
    return {
        "reference_id": reference["reference_id"],
        "derived_operation_cases": 81,
        "derived_operation_differences": pair_differences,
        "scoped_operation_definitions_passed": not pair_differences,
        "source_clause_count": 216,
        "source_role_count_required": 432,
        "source_role_count_checked": len(terms),
        "source_role_matches": sum(r["matched"] is True for r in terms),
        "source_role_differences": [r for r in terms if r["matched"] is False],
        "source_role_ambiguous": [r for r in terms if r["matched"] is None],
        "complete_literal_relation_acceptance_passed": all(
            r["matched"] is True for r in terms
        ),
        "comparison_basis": "axis_pair_as_defined_p453_p910",
        "per_case_basis_substitution_used": False,
        "source_angle_applicability_verified": False,
        "whole_book_conformity_established": False,
        "real_world_prediction_established": False,
        "scope": "81主客五行算法条件和216条下卦关系词；不是81对专属断语、全书统一吉凶或现实预测验证",
    }
