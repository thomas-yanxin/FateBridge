"""Audit the frozen pair-enclosure branch without certifying the whole family."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_enclosures import general_pair_enclosures
from fatebridge.core.metaphysics.taiyi_year import cyclic_core

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/taiyi_jinjing_v17"
MANIFEST_SHA256 = "f85c4d71677b4c94cad17da3c480614af0f5a4e4c7a18057f53b29fe8e04200e"
CORRECTION_SHA256 = "d895b92534aba94f5fdbd2bccf825ccb3db4e96fd7c1906376a631689ac58c30"


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest_file = corpus / "manifest.json"
    if hashlib.sha256(manifest_file.read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise ValueError("原典清单指纹不符")
    manifest = json.loads(manifest_file.read_text())
    for row in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("原典文件指纹不符：" + row["file"])
    for row in manifest["prior_source_references"]:
        if (
            hashlib.sha256((CORPUS.parent / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("先前原典指纹不符：" + row["file"])
    correction_file = corpus / "correction-manifest.json"
    if hashlib.sha256(correction_file.read_bytes()).hexdigest() != CORRECTION_SHA256:
        raise ValueError("订正清单指纹不符")
    correction_manifest = json.loads(correction_file.read_text())
    if correction_manifest["original_manifest_sha256"] != MANIFEST_SHA256:
        raise ValueError("初录清单引用指纹不符")
    for row in correction_manifest["source_files"]:
        if (
            hashlib.sha256((corpus / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("订正依据指纹不符")
    corrections = json.loads((corpus / "name-map-corrections.json").read_text())[
        "corrections"
    ]
    proof = (corpus / "name-map-proof.txt").read_text()
    if len(corrections) != 4 or not all(c["proof_quote"] in proof for c in corrections):
        raise ValueError("四处神名订正缺少独立卷二名表")
    cases = json.loads((corpus / "worked-cases.json").read_text())
    mentions = json.loads((corpus / "mention-readings.json").read_text())
    worked = []
    initial_matches = 0
    for case in cases:
        core = cyclic_core(case["source_ju"])
        expected = case["expected_pair_enclosure"]
        found = [
            p
            for p in general_pair_enclosures(core)
            if p["subject"] == expected["subject"]
            and p["basis"][0]["field"] == "core_board." + expected["camp"] + "_general"
        ]
        initial_matches += sum(core[k] == v for k, v in case["expected_core"].items())
        corrected = dict(case["expected_core"])
        for correction in corrections:
            if correction["case_id"] == case["id"]:
                if corrected[correction["field"]] != correction["original_value"]:
                    raise ValueError("须保留神名初录，不能覆写初始预期")
                corrected[correction["field"]] = correction["corrected_value"]
        numeric = [
            {"field": k, "expected": v, "computed": core[k], "matches": v == core[k]}
            for k, v in corrected.items()
        ]
        worked.append(
            {
                "id": case["id"],
                "source_ju": case["source_ju"],
                "source_year_ce_label": case["source_year_ce_label"],
                "numeric_observations": numeric,
                "pair_enclosure_matches": len(found) == 1,
                "unadjudicated": case.get("unadjudicated", []),
            }
        )
    observations = []
    for row in mentions:
        core = cyclic_core(row["ju"])
        matching = [
            p
            for p in general_pair_enclosures(core)
            if p["subject"] == row["subject"]
            and p["basis"][0]["field"]
            == "core_board." + row["flanking_camp"] + "_general"
        ]
        observations.append(
            {
                **row,
                "computed_pair_enclosures": matching,
                "matches": len(matching) == 1,
            }
        )
    return {
        "completion_claim": False,
        "source_manifest_sha256": MANIFEST_SHA256,
        "correction_manifest_sha256": CORRECTION_SHA256,
        "initial_transcription_matching_observations": initial_matches,
        "name_map_corrections": corrections,
        "independent_worked_cases": len(worked),
        "worked_case_numeric_observations": sum(
            len(c["numeric_observations"]) for c in worked
        ),
        "worked_case_matching_numeric_observations": sum(
            o["matches"] for c in worked for o in c["numeric_observations"]
        ),
        "worked_pair_enclosures_matching": sum(
            c["pair_enclosure_matches"] for c in worked
        ),
        "worked_cases": worked,
        "all_yang_literal_mentions": len(observations),
        "unique_mentioned_cyclic_ju": len({r["ju"] for r in mentions}),
        "unique_camp_target_observations": len(
            {(r["ju"], r["flanking_camp"], r["target_field"]) for r in mentions}
        ),
        "matching_literal_mentions": sum(r["matches"] for r in observations),
        "observations": observations,
        "count_policy": "2书影源例与17处循环注分别统计；后者11局16唯一目标，不作17独立命盘，未列不当否定。",
        "source_reliability": "图70两例已核书影；循环17处为原典转录，未冒认均覆核书影。",
        "whole_family_acceptance_passed": False,
        "whole_book_conformance": "not_established",
        "historical_calendar_reconstructed": False,
        "full_judgment_validated": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
