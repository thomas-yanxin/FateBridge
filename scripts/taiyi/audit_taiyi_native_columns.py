"""Audit frozen native-facsimile semantic readings, never generate expectations."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v23"
MANIFEST_SHA = "62a40d4517386efea5557598b081aab1e99a1db1d8b58895ae8901ab8a54eced"
CORRECTION_SHA = "fe5acfabb611c2b65563315c431a20b9c929380243a16882ba1f575976b2b778"
POSITION_FIELDS = ("taiyi_number", "wenchang_palace", "shiji", "jishen")
COUNT_FIELDS = ("main_count", "guest_count")
GENERAL_FIELDS = (
    "main_general",
    "main_vice_general",
    "guest_general",
    "guest_vice_general",
)


def source_readings(corpus: Path = CORPUS) -> dict[str, Any]:
    """Read source-only values; preserve the initial file and apply logged errata."""
    for name, fingerprint in (
        ("manifest.json", MANIFEST_SHA),
        ("correction-manifest.json", CORRECTION_SHA),
    ):
        raw = (corpus / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != fingerprint:
            raise ValueError("书影校读清单指纹不符")
        manifest = json.loads(raw)
        if (
            name != "manifest.json"
            and manifest["original_manifest_sha256"] != MANIFEST_SHA
        ):
            raise ValueError("书影初录引用指纹不符")
        for item in manifest["source_files"]:
            if (
                hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
                != item["sha256"]
            ):
                raise ValueError("书影校读材料指纹不符：" + item["file"])
    manifest = json.loads((corpus / "manifest.json").read_text())
    for item in manifest["reference_files"]:
        if (
            hashlib.sha256((CORPUS.parent / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("同书名位参考指纹不符")
    reference = json.loads((corpus / "name-reference.json").read_text())
    corrections = json.loads((corpus / "reading-corrections.json").read_text())
    if (
        corrections["original_reading_sha256"]
        != hashlib.sha256((corpus / "native-columns.tsv").read_bytes()).hexdigest()
    ):
        raise ValueError("书影初录指纹不符")
    with (corpus / "native-columns.tsv").open() as source:
        raw_rows = list(csv.DictReader(source, delimiter="\t"))
    rows = []
    applied = []
    for raw_row in raw_rows:
        row = dict(raw_row)
        identity = f"{row['polarity']}-{int(row['ju']):02d}"
        for correction in corrections["entries"]:
            if correction["id"] != identity:
                continue
            field = correction["field"]
            if (
                int(row[field]) != correction["initial"]
                or int(row["page"]) != correction["page"]
                or row["columns_from_right"] != correction["columns_from_right"]
            ):
                raise ValueError("订正与初录或栏位不符")
            row[field] = str(correction["selected"])
            applied.append((identity, field))
        positions = {
            "taiyi_number": int(row["taiyi_number"]),
            "wenchang_palace": reference["prefix_to_position"][row["wenchang_name"]],
            "shiji": reference["prefix_to_position"][row["shiji_name"]],
            "jishen": row["jishen"],
        }
        counts = {field: int(row[field]) for field in COUNT_FIELDS}
        if (
            row["polarity"] not in {"yang", "yin"}
            or positions["taiyi_number"] not in {1, 2, 3, 4, 6, 7, 8, 9}
            or positions["jishen"] not in set("子丑寅卯辰巳午未申酉戌亥")
            or any(not 1 <= n <= 40 for n in counts.values())
            or not 106 <= int(row["page"]) <= 124
        ):
            raise ValueError("书影行身份、栏位或取值无效")
        rows.append(
            {
                "id": identity,
                "yin": row["polarity"] == "yin",
                "ju": int(row["ju"]),
                "page": int(row["page"]),
                "columns_from_right": [
                    int(n) for n in row["columns_from_right"].split(",")
                ],
                "positions": positions,
                "table_counts": counts,
                "printed_generals": {
                    field: int(row[field]) if row[field] else None
                    for field in GENERAL_FIELDS
                },
            }
        )
    if len(rows) != 144 or {(r["yin"], r["ju"]) for r in rows} != {
        (yin, ju) for yin in (False, True) for ju in range(1, 73)
    }:
        raise ValueError("不得移除阴阳144局")
    if len(applied) != 4 or len(set(applied)) != 4:
        raise ValueError("不得丢失或重复四项初录订正")
    return {
        "manifest": manifest,
        "reference": reference,
        "corrections": corrections,
        "rows": rows,
    }


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    # Runtime is imported only after the separately frozen source can be read.
    data = source_readings(corpus)
    from fatebridge.core.metaphysics.taiyi_year import cyclic_core

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
