"""Bind all384source locators and six concise editorial paraphrases.

No domain calculator imports. Labels and polarity facts use the separately
frozen factual catalogue; these paraphrases are not independent adjudication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from scripts.audit_human_design_source_clauses import SOURCE_SHA256, line_blocks

ROOT = Path(__file__).resolve().parents[1]
DEPTH = ROOT / "src/fatebridge/data/human_design/rave-2001-depth.json"
DEPTH_SHA256 = "6fd06279b49f071dabb34aa293070f51f840cd1773986304aecbbbaa6be2270b"
OUTPUT = ROOT / "src/fatebridge/data/human_design/line-knowledge-v1.json"
# Local editorial summaries of the two printed poles, not quotations, tested
# personality traits, advice, predictions, or a replacement for the full text.
CURATED = {
    1: ("创作时机", "表达有其时机，重视适应。", "不耐与不稳定可能干扰创造。"),
    2: ("价值与灵感", "价值与理想协调，滋养表达。", "欲望与激情可能压缩创造。"),
    3: ("持续表达", "维持自我表达的深层需要。", "物质与过度野心可能打断创造。"),
    4: ("独处与创造", "创造需要不受外界牵引的空间。", "急于施加影响可能限制创造。"),
    5: ("创作耐力", "耐力与驱动力支撑创作坚持。", "奇异吸引力也可能削弱持久推进。"),
    6: ("创造价值的评估", "清楚评估创作价值。", "主观评判可能带来创作挫折。"),
}


def build(pdf: Path) -> dict:
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Different public source copy; edition review required")
    if hashlib.sha256(DEPTH.read_bytes()).hexdigest() != DEPTH_SHA256:
        raise ValueError("Original factual catalogue changed")
    catalog = json.loads(DEPTH.read_bytes())
    layout = subprocess.check_output(["pdftotext", "-layout", str(pdf), "-"], text=True)
    blocks = {(g, line): (page, text) for g, line, page, text in line_blocks(layout)}
    rows = []
    for gate in range(1, 65):
        for line in range(1, 7):
            page, text = blocks[gate, line]
            item = {
                "key": f"{gate}.{line}",
                "gate": gate,
                "line": line,
                "source_pdf_page_one_based": page,
                "source_layout_block_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "meaning_status": "not_yet_curated",
                "editorial_paraphrase": None,
                "independent_semantic_review_completed": False,
                "complete_line_meaning_accepted": False,
                "source_reading_notes": [],
            }
            if gate == 1:
                title, up, down = CURATED[line]
                item.update(
                    meaning_status="local_editorial_paraphrase_pending_independent_review",
                    editorial_paraphrase={
                        "theme_zh": title,
                        "exaltation": up,
                        "detriment": down,
                    },
                )
                if line == 4:
                    item["source_reading_notes"] = [
                        "上升段与下降段有重复措辞，按末句作有限转述；未据此修订原文或宣布歧义已解决。"
                    ]
            rows.append(item)
    return {
        "schema_version": 1,
        "catalogue_id": "human_design_line_knowledge_v1",
        "version": 1,
        "source": {
            key: value for key, value in catalog["source"].items() if key != "scope"
        },
        "source_factual_catalogue_sha256": DEPTH_SHA256,
        "curated_by": "FateBridge root-agent local editorial review of fixed public copy",
        "curated_on": "2026-10-27",
        "required_line_count": 384,
        "local_paraphrase_count": 6,
        "independently_accepted_line_count": 0,
        "publisher_master_authenticated": False,
        "complete384_line_meanings_accepted": False,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(args.pdf), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check:
        if args.output.read_bytes() != raw:
            raise SystemExit("Source locators or editorial reference changed")
    else:
        args.output.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
