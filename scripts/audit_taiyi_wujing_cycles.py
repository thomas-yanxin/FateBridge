"""Compare all 144 Wujing cycle descriptions, retaining all 1,440 targets.

The frozen extraction precedes this audit and imports no production algorithm.
Source words, explicit values, name normalization, and runtime facts stay apart.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_year import RULESET_ID, cyclic_core

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v22"
MANIFEST_SHA256 = "e9d33f823e9c1810249b5d02ad0e50b5a4e69a1549c9cbbc7723bc34d76363d8"
NAME_MANIFEST_SHA256 = (
    "3aecfdc0742e8f8ea201348d7dedae14d4d5510771b78f93f16aac1c4ebc37e3"
)
FACSIMILE_MANIFEST_SHA256 = (
    "027570d862636f04b9b77ac916860341d9c29b251888232640f8284c3debe848"
)
FIELDS = (
    "taiyi_number",
    "main_count",
    "guest_count",
    "wenchang_name",
    "shiji_name",
    "jishen",
    "main_general",
    "main_vice_general",
    "guest_general",
    "guest_vice_general",
)
ACTUAL_FIELDS = {"wenchang_name": "wenchang_palace", "shiji_name": "shiji"}


def _manifest(directory: Path, name: str, expected: str) -> dict[str, Any]:
    raw = (directory / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"武经来源清单指纹漂移：{name}")
    data: dict[str, Any] = json.loads(raw)
    for filename, fingerprint in data["files"].items():
        if Path(filename).name != filename:
            raise ValueError("来源文件必须位于同一封存目录")
        if (
            hashlib.sha256((directory / filename).read_bytes()).hexdigest()
            != fingerprint
        ):
            raise ValueError(f"武经来源文件指纹漂移：{filename}")
    return data


def source_data(corpus: Path = CORPUS) -> dict[str, Any]:
    _manifest(corpus, "manifest.json", MANIFEST_SHA256)
    reference_manifest = _manifest(
        corpus, "name-reference-manifest.json", NAME_MANIFEST_SHA256
    )
    _manifest(corpus, "facsimile-manifest.json", FACSIMILE_MANIFEST_SHA256)
    reference = CORPUS.parent / reference_manifest["reference_file"]
    if (
        hashlib.sha256(reference.read_bytes()).hexdigest()
        != reference_manifest["reference_sha256"]
    ):
        raise ValueError("十六神名位补证指纹漂移")
    data: dict[str, Any] = json.loads(
        (corpus / "wujing-literal-cycles.json").read_text()
    )
    keys = [(r["polarity"], r["ju"]) for r in data["rows"]]
    if len(keys) != 144 or set(keys) != {
        (polarity, ju) for polarity in ("yang", "yin") for ju in range(1, 73)
    }:
        raise ValueError("阴阳两套72局必须全部保留")
    if any(
        len(row["observations"]) != 10
        or {o["field"] for o in row["observations"]} != set(FIELDS)
        for row in data["rows"]
    ):
        raise ValueError("全部1440个待核字段必须保留，未知不得删去")
    data["name_reference"] = json.loads((corpus / "name-reference.json").read_text())
    data["source_metadata"] = json.loads((corpus / "source-metadata.json").read_text())
    data["facsimile_supplement"] = json.loads(
        (corpus / "facsimile-supplement.json").read_text()
    )
    return data


def source_value(
    observation: dict[str, Any], reference: dict[str, Any]
) -> dict[str, Any]:
    """Resolve only declared labels, never pick the name matching a runtime value."""
    field, raw = observation["field"], observation["value"]
    if observation["status"] in {"ambiguous", "not_stated_or_unparsed"}:
        return {
            "status": "not_resolved",
            "value": None,
            "reason": observation["status"],
        }
    if field in {"wenchang_name", "shiji_name"}:
        candidates = [
            (name, position)
            for name, position in reference["prefix_to_position"].items()
            if isinstance(raw, str) and raw.startswith(name)
        ]
        if len(candidates) != 1:
            return {
                "status": "not_resolved",
                "value": None,
                "reason": "unmapped_or_ambiguous_literal_name_prefix",
            }
        name, position = candidates[0]
        return {
            "status": "declared_name_prefix_position_reference",
            "value": position,
            "literal_name_prefix": name,
            "unadjudicated_attached_text": raw[len(name) :],
            "name_reference_file": reference["reference_file"],
            "whole_annotation_conformance_assessed": False,
        }
    return {"status": observation["status"], "value": raw}


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    data = source_data(corpus)
    # Source-only diagnostic; no source or runtime values are replaced.
    repeated_fields = (
        "main_count",
        "guest_count",
        "main_general",
        "main_vice_general",
        "guest_general",
        "guest_vice_general",
        "shiji_name",
    )
    repetitions = []
    for previous, current in zip(data["rows"], data["rows"][1:]):
        if previous["polarity"] != current["polarity"]:
            continue
        left = {o["field"]: o["value"] for o in previous["observations"]}
        right = {o["field"]: o["value"] for o in current["observations"]}
        if (
            left["wenchang_name"] is not None
            and right["wenchang_name"] is not None
            and left["wenchang_name"] != right["wenchang_name"]
            and all(
                left[f] is not None and left[f] == right[f] for f in repeated_fields
            )
        ):
            repetitions.append(
                {
                    "source_ids": [previous["id"], current["id"]],
                    "different_wenchang_readings": [
                        left["wenchang_name"],
                        right["wenchang_name"],
                    ],
                    "identical_literal_fields": {f: left[f] for f in repeated_fields},
                    "is_error_adjudicated": False,
                    "source_or_runtime_values_replaced": False,
                }
            )
    rows = []
    totals = {
        f: {"required": 144, "matching": 0, "different": 0, "unknown": 0}
        for f in FIELDS
    }
    for row in data["rows"]:
        core = cyclic_core(row["ju"], yin=row["polarity"] == "yin")
        comparisons = []
        for observation in row["observations"]:
            field = observation["field"]
            resolved = source_value(observation, data["name_reference"])
            actual_field = ACTUAL_FIELDS.get(field, field)
            actual = core[actual_field]
            status = (
                "unknown"
                if resolved["value"] is None
                else "matching" if resolved["value"] == actual else "different"
            )
            totals[field][status] += 1
            comparisons.append(
                {
                    "source_observation": observation,
                    "resolved_source": resolved,
                    "actual_field": actual_field,
                    "actual_value": actual,
                    "comparison_status": status,
                }
            )
        rows.append(
            {
                "id": row["id"],
                "polarity": row["polarity"],
                "ju": row["ju"],
                "source_heading": row["source_heading"],
                "source_block": row["source_block"],
                "comparisons": comparisons,
                "whole_annotation_conformance_assessed": False,
            }
        )
    differences = [
        {"id": row["id"], **comparison}
        for row in rows
        for comparison in row["comparisons"]
        if comparison["comparison_status"] == "different"
    ]
    unknowns = [
        {"id": row["id"], **comparison}
        for row in rows
        for comparison in row["comparisons"]
        if comparison["comparison_status"] == "unknown"
    ]
    return {
        "completion_claim": False,
        "audit_id": "wujing_144_literal_fields_v1",
        "audit_version": "1.0.0",
        "audit_author": "FateBridge contributors",
        "actual_rule_profile": {
            "id": RULESET_ID,
            "scope": "与现用金镜循环核心作跨书比较；不是另行实现或宣称已符合武经全部规则。",
        },
        "source_manifest_sha256": MANIFEST_SHA256,
        "name_reference_manifest_sha256": NAME_MANIFEST_SHA256,
        "facsimile_manifest_sha256": FACSIMILE_MANIFEST_SHA256,
        "source_metadata": data["source_metadata"],
        "facsimile_supplement": data["facsimile_supplement"],
        "required_rows": 144,
        "audited_rows": len(rows),
        "required_observations": 1440,
        "field_totals": totals,
        "differences": differences,
        "unknowns": unknowns,
        "adjacent_source_pairs_considered": 142,
        "adjacent_literal_repetitions": repetitions,
        "repetition_policy": "同阴阳相邻局的天目录文不同而七项录值相同，只列来源重复；未判定沿抄错误，不按软件或前后局补值，不算新增古例。",
        "source_rows": rows,
        "count_policy": "按十类字段分别统计；144行是循环局注，不是144个有日期古例。抄录正文不计计算命中，未知仍留在1440要求中，不以不同字段总和构造原典准确率。",
        "name_policy": data["name_reference"]["scope"],
        "source_outcomes_applied": False,
        "production_arithmetic_changed_by_this_audit": False,
        "copied_source_blocks_counted_as_calculated_hits": 0,
        "new_dated_cases": 0,
        "whole_annotation_conformance_assessed": False,
        "whole_classic_acceptance_passed": False,
        "prior_jinjing_disagreements_resolved_by_switching_sources": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
