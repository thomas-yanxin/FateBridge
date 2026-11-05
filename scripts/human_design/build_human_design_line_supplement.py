"""Add a bounded Gate2 editorial supplement without rewriting the v1 source.

This is a reproducible packaging check, not independent semantic acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from scripts.human_design.audit_human_design_source_clauses import (
    SOURCE_SHA256,
    line_blocks,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src/fatebridge/data/human_design"
BASE_SHA256 = "e0be8121e433f1513fdd45ac560acd4c7519f67cf12d11bd86b966b0e011430e"
CURATED = {
    1: ("审美与直觉", "以美感感知和谐方向。", "自我主张可能压过内在判断。"),
    2: ("自发领会", "自发领会与内在专注。", "把知识当作强化自我的权力。"),
    3: ("接纳与耐心", "持续接纳学习，承认过程不终结。", "急于表达，不愿等待。"),
    4: ("审慎表达", "不求个人声望，以分寸维持和谐。", "急于张扬可能引来对立。"),
    5: ("资源与策略", "理性配置资源，运用策略。", "独揽责任，忽略他人能力。"),
    6: ("视野与安全", "理性解释也可能使接纳视野狭窄。", "过度求安全可能扭曲觉察。"),
}


def encoded(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def build(pdf: Path) -> tuple[dict, dict]:
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Different public source copy; edition review required")
    raw = (DATA / "line-knowledge-v1.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError("Never rewrite the frozen v1 catalogue")
    base = json.loads(raw)
    layout = subprocess.check_output(["pdftotext", "-layout", str(pdf), "-"], text=True)
    blocks = {(g, line): (page, text) for g, line, page, text in line_blocks(layout)}
    rows = []
    for line, (theme, up, down) in CURATED.items():
        original = base["rows"][6 + line - 1]
        page, text = blocks[2, line]
        if (
            page != 9
            or hashlib.sha256(text.encode()).hexdigest()
            != original["source_layout_block_sha256"]
        ):
            raise ValueError("Supplement source block differs from original locator")
        row = {
            "key": f"2.{line}",
            "source_pdf_page_one_based": page,
            "source_layout_block_sha256": original["source_layout_block_sha256"],
            "meaning_status": "local_editorial_paraphrase_pending_independent_review",
            "editorial_paraphrase": {
                "theme_zh": theme,
                "exaltation": up,
                "detriment": down,
            },
            "independent_semantic_review_completed": False,
            "complete_line_meaning_accepted": False,
            "source_reading_notes": [],
        }
        if line == 3:
            normalized = " ".join(text.split())
            clause = re.search(
                r"When connected permanently to Gate 14 through the Beat Channel, rewards for services rendered\.",
                normalized,
            )
            if clause is None:
                raise ValueError("Original conditional clause not observed")
            row["source_conditions"] = [
                {
                    "id": "rave2001_2_3_exaltation_permanent_2_14",
                    "polarity": "exaltation",
                    "source_clause_sha256": hashlib.sha256(
                        clause.group().encode()
                    ).hexdigest(),
                    "source_condition": {
                        "relation": "permanent_channel_connection",
                        "channel_gates": [2, 14],
                    },
                    "local_clause_paraphrase_zh": "原文在永久连接14门、形成2–14通道的条件下谈服务回报；不是无条件事件预告，也未据此断定逆命题。",
                    "personal_condition_satisfied": None,
                    "automatic_application": False,
                    "evidence_required": [
                        "same_run_actual_2_3_activation_and_fixing_state",
                        "same_run_permanent_2_14_channel_evidence",
                    ],
                    "review_status": "local_clause_review_pending_independent_review",
                }
            ]
            row["condition_review_status"] = (
                "one_explicit_clause_locally_recorded_not_exhaustive"
            )
        if line == 6:
            row["source_reading_notes"] = [
                "本条上升段也描述接纳视野狭窄，不把上升一概改写为正面能力。"
            ]
        rows.append(row)
    supplement = {
        "schema_version": 1,
        "supplement_id": "human_design_gate2_editorial_v1",
        "base_catalogue_sha256": BASE_SHA256,
        "source_pdf_sha256": SOURCE_SHA256,
        "curated_by": "FateBridge root-agent local editorial review of fixed public copy",
        "curated_on": "2026-10-27",
        "independently_accepted_line_count": 0,
        "publisher_master_authenticated": False,
        "complete384_line_meanings_accepted": False,
        "rows": rows,
    }
    manifest = {
        "schema_version": 1,
        "catalogue_id": "human_design_line_knowledge_v2",
        "version": 2,
        "base": {"file": "line-knowledge-v1.json", "sha256": BASE_SHA256},
        "supplements": [
            {
                "file": "line-knowledge-gate2-v1.json",
                "sha256": hashlib.sha256(encoded(supplement)).hexdigest(),
                "keys": [r["key"] for r in rows],
            }
        ],
        "required_line_count": 384,
        "expected_local_paraphrase_count": 12,
        "independently_accepted_line_count": 0,
        "publisher_master_authenticated": False,
        "complete384_line_meanings_accepted": False,
    }
    return supplement, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    supplement, manifest = build(args.pdf)
    for name, value in [
        ("line-knowledge-gate2-v1.json", supplement),
        ("line-knowledge-manifest-v2.json", manifest),
    ]:
        raw = encoded(value)
        path = DATA / name
        if args.check:
            if path.read_bytes() != raw:
                raise SystemExit(f"Bound source supplement changed: {name}")
        elif path.exists():
            raise FileExistsError(f"Never overwrite a source revision: {path}")
        else:
            path.write_bytes(raw)
        print(name, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
