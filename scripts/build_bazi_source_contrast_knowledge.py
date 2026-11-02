"""Build one additive source-contrast card without inferring source judgments."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_source_contrast_knowledge_v1"
DESTINATION = ROOT / "src/fatebridge/data/knowledge/bazi-source-contrasts.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_bundle():
    path = FIXTURE / "protocol.json"
    if sha(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Contrast knowledge protocol changed")
    protocol = json.loads(path.read_text())
    source = FIXTURE / "source-bindings.json"
    if sha(source) != protocol["source_bindings_sha256"]:
        raise ValueError("All15/14 source contrast bindings changed")
    bindings = json.loads(source.read_text())
    analysis_path = ROOT / bindings["source_analysis"]
    if sha(analysis_path) != bindings["source_analysis_sha256"]:
        raise ValueError("Frozen contrast analysis changed")
    analysis = json.loads(analysis_path.read_text())
    rows = bindings["all15_printed_pair_results"]
    relational = bindings["all14_unprinted_relational_cases"]
    if (
        rows != analysis["printed_pair_results"]
        or len(rows) != 15
        or relational != analysis["all14_unprinted_relational_cases_retained"]
        or len(relational) != 14
    ):
        raise ValueError("Knowledge source inventory narrowed")
    if any(any(c["literal_pillars"].values()) for c in relational):
        raise ValueError("Unprinted source alternatives must stay unprinted")
    reference_path = analysis_path.parent / "reference-first.json"
    parent = json.loads((analysis_path.parent / "protocol-first.json").read_text())
    if (
        sha(analysis_path.parent / "protocol-first.json")
        != bindings["source_protocol_sha256"]
        or sha(reference_path) != parent["independent_reference_sha256"]
    ):
        raise ValueError("Correspondence reference lost original protocol binding")
    pages = sorted({n for row in rows for n in row["source_pages"]})
    source_url = "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf"
    curation = {
        "method_id": protocol["method_id"],
        "entry_revision": 1,
        "classification": "source_literals_plus_explicit_symbolic_dependencies_not_causal_evidence",
        **{
            k: protocol[k]
            for k in [
                "source_tip_indices",
                "implementation_tip_indices",
                "editorial_tip_indices",
            ]
        },
        "source_refs": [
            {
                "author": "任鐵樵增注（任氏曰）",
                "title": "任注滴天髓闡微·命例比较",
                "edition": "李雨田校訂，上海大東書局，1947年4月初版",
                "source_url": source_url,
                "source_sha256": protocol["source_pdf_sha256"],
                "source_pdf_pages": pages,
                "support_scope": "只支持这些原图四柱、比较语和位置；配干联动为独立列明的符号分析，不认证作者意图、人物事迹或因果效果。",
            },
            {
                "author": "李雨田增補",
                "title": "初學捷徑·遁月遁時（收入任注滴天髓闡微）",
                "edition": "李雨田校訂，上海大東書局，1947年4月初版",
                "source_url": source_url,
                "source_sha256": protocol["source_pdf_sha256"],
                "source_pdf_pages": [32, 34, 35, 36],
                "support_scope": "只支持年干配月、日干配时及本书夜子候选，不能据干支反推出唯一现代出生日期或钟点。",
            },
        ],
        "implementation_refs": [
            {
                "source_path": "scripts/audit_bazi_source_contrast_dependencies.py",
                "source_sha256": analysis["runner_sha256"],
                "support_scope": "只支持逐位差异、配月配时表联动、六十甲子和缺项候选的符号核查；没有新增强弱计算或现实预测验收。",
            }
        ],
        "source_contrast_binding": {
            "source_analysis_sha256": sha(analysis_path),
            "source_bindings_sha256": sha(source),
            "all15_printed_pairs": copy.deepcopy(rows),
            "all14_unprinted_relational_cases": copy.deepcopy(relational),
            "correspondence_reference_sha256": sha(reference_path),
            "all_original_questions_retained": copy.deepcopy(
                bindings["all_original_questions_retained"]
            ),
            "source_questions_closed": 0,
            "force_comparison_allowed": False,
            "causal_acceptance": False,
        },
        "validation_status": "source_bound_symbolic_contrasts_not_causal_or_force_acceptance",
        "review_status": "single_developer_source_reading_external_review_pending",
        "independent_expert_review": "not_completed",
        "reality_prediction_efficacy": "not_tested",
        "source_attribution_rule": "原图与任氏比较语、李氏配干表、程序符号分析及编辑边界分开；保留全部字面差异与原疑问。",
        "citation": "FateBridge限域编释，非逐字引文；任鐵樵增注、李雨田校訂《任注滴天髓闡微》，上海大東書局1947年4月初版；"
        + source_url
        + "；原图比较不认证单一现实因果、完整强弱算法或预测有效性。",
        "curated_on": protocol["utc"][:10],
    }
    return {
        "schema_version": 1,
        "id": "fatebridge_bazi_source_contrasts_v1",
        "version": 1,
        "domain": "bazi",
        "description": "独立新增的原典比较与配干联动知识；原85条八字及3条基础概念保持原值。",
        "categories": {
            protocol["category"]: {
                protocol["key"]: {
                    "title": protocol["key"],
                    "tips": protocol["tips_frozen_before_build"],
                    "curation": curation,
                }
            }
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = expected_bundle()
    actual = json.loads(DESTINATION.read_text()) if DESTINATION.exists() else None
    if args.check:
        if actual != expected:
            print("FAIL: source contrast supplement absent or changed")
            return 1
        print("PASS: one card retains all15 printed and14 unprinted source bindings")
        return 0
    if actual not in (None, expected):
        raise ValueError("Source contrast supplement changed concurrently")
    DESTINATION.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
    print("Built separately declared source contrast knowledge supplement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
