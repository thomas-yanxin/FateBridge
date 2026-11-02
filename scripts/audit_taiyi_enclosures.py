"""Audit the complete selected NCL worked example, keeping source corrections.

This selected geometry can pass; the whole enclosure family is not complete.
The command therefore still exits 1 instead of certifying the whole classic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_enclosures import principal_enclosures
from fatebridge.core.metaphysics.taiyi_year import yearly_core

CORPUS = Path(__file__).resolve().parents[1] / "tests/fixtures/taiyi_jinjing_v11"
NUMERIC_FIELDS = {
    "taiyi_number",
    "taiyi_palace",
    "wenchang_palace",
    "jishen",
    "shiji",
    "main_count",
    "main_general",
    "main_vice_general",
    "guest_count",
    "guest_general",
    "guest_vice_general",
}


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    corpus = corpus.resolve()
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    correction_manifest = json.loads((corpus / "correction-manifest.json").read_text())
    if (
        hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        != correction_manifest["original_manifest_sha256"]
    ):
        raise ValueError("原始初录清单指纹不符")
    for item in manifest["source_files"] + correction_manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError(f"原典文件指纹不符：{item['file']}")
    case = json.loads((corpus / "principal-enclosure.json").read_text())
    correction = json.loads((corpus / "transcription-correction.json").read_text())
    if set(case["expected"]) != NUMERIC_FIELDS or len(case["enclosures"]) != 2:
        raise ValueError("须保留完整11项宫数及2个原文明载提挟目标")
    if (case["year_ce"], case["ju"], case["source_page"]) != (385, 70, 51):
        raise ValueError("须保留太元十年乙酉原例，不改为更容易通过的课例")
    if (
        correction["original_field"] != "expected.wenchang_palace"
        or (correction["original_value"], case["expected"]["wenchang_palace"])
        != ("亥", "亥")
        or correction["corrected_value"] != "未"
    ):
        raise ValueError("天道初录订正不符")
    proof = (corpus / correction["proof_file"]).read_text()
    if not all(text in proof for text in ("未神曰天道", "亥神曰大義")):
        raise ValueError("缺少卷二天道/大义独立名称映射")
    core = yearly_core(case["year_ce"])
    initial = {key: core[key] == value for key, value in case["expected"].items()}
    corrected = {**case["expected"], "wenchang_palace": correction["corrected_value"]}
    observations = [
        {
            "field": key,
            "source_value": value,
            "computed_value": core[key],
            "matches": core[key] == value,
        }
        for key, value in corrected.items()
    ]
    found = []
    palaces = {
        1: "乾",
        2: "午",
        3: "艮",
        4: "卯",
        5: "中",
        6: "酉",
        7: "坤",
        8: "子",
        9: "巽",
    }
    for p in principal_enclosures(core):
        fields = p["basis"]
        found.append(
            {
                "subject": p["subject"],
                "flanking_general": p["variant"].split("与", 1)[1].split("夹", 1)[0],
                "taiyi_palace": fields[0]["value"],
                "general_palace": palaces[fields[1]["value"]],
                "target_palace": (
                    palaces[fields[2]["value"]]
                    if type(fields[2]["value"]) is int
                    else fields[2]["value"]
                ),
            }
        )
    enclosures_match = found == case["enclosures"]
    return {
        "completion_claim": False,
        "independent_classical_cases": 1,
        "historical_label": case["historical_label"],
        "source_url": case["source_url"],
        "source_page": case["source_page"],
        "required_numeric_observations": 11,
        "initial_transcription_matches": sum(initial.values()),
        "initial_transcription_disagreements": [
            key for key, ok in initial.items() if not ok
        ],
        "source_correction": correction,
        "matching_numeric_observations": sum(r["matches"] for r in observations),
        "observations": observations,
        "source_ju_matches": core["kook_number"] == case["ju"],
        "required_enclosure_targets": 2,
        "source_enclosure_targets": case["enclosures"],
        "computed_enclosure_targets": found,
        "enclosure_targets_match": enclosures_match,
        "selected_example_geometry_passed": enclosures_match
        and core["kook_number"] == case["ju"]
        and all(r["matches"] for r in observations),
        "whole_enclosure_family_acceptance_passed": False,
        "unadjudicated": ["四郭固", "四郭杜", "挟闭", "内外生死等后续完整断语"],
        "historical_calendar_reconstructed": False,
        "public_default_ancient_annual_adapter_supported": False,
        "explicit_historical_year_profile_available": True,
        "scope": "循环核心原例数值与明确正宫提挟几何；默认公共年计依然受通用农历范围约束；V12明确历史历表配置另验，不以古例循环数值匹配冒充历史日期验收。",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw)
    raise SystemExit(0 if result["whole_enclosure_family_acceptance_passed"] else 1)


if __name__ == "__main__":
    main()
