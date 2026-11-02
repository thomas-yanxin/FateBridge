"""Render one source-bound knowledge card; do not infer numerical strength."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_body_vocabulary_knowledge_v3"
BUNDLE = ROOT / "src/fatebridge/data/knowledge/bazi.json"
CATEGORY = "classical_force_semantics"
KEY = "日元强弱与性情措辞"
STATES = ("太旺", "旺極", "太衰", "衰極")
WORDS = {"旺極": "旺极", "衰極": "衰极", "煉": "炼", "剋": "克", "濟": "济"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_card():
    protocol_path = FIXTURE / "protocol.json"
    if (
        digest(protocol_path)
        != protocol_path.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Four-state protocol changed")
    protocol = json.loads(protocol_path.read_text())
    source = FIXTURE / "source-relations.json"
    if digest(source) != protocol["frozen20_relation_reference_sha256"]:
        raise ValueError("Frozen source relations changed")
    reference = json.loads(source.read_text())
    rows = reference["rows"]
    indexed = {(row["element"], row["source_state"]): row for row in rows}
    if len(rows) != 20 or set(indexed) != {
        (element, state) for element in "木火土金水" for state in STATES
    }:
        raise ValueError(
            "The complete five-element four-state relation table is required"
        )
    before = FIXTURE / "before/src/fatebridge/data/knowledge/bazi.json"
    if digest(before) != protocol["before_files_sha256"][str(BUNDLE.relative_to(ROOT))]:
        raise ValueError("Historical revision2 changed")
    old = json.loads(before.read_text())["categories"][CATEGORY][KEY]
    result = copy.deepcopy(old)
    groups = []
    for element in "木火土金水":
        relations = []
        for state in STATES:
            row = indexed[element, state]
            if row["numeric_threshold"] is not None or row["implemented_or_evaluated"]:
                raise ValueError(
                    "Text relations cannot certify computed four-state thresholds"
                )
            relations.append(
                f"{WORDS.get(state, state)}似{row['analogous_element']}"
                f"宜{row['preferred_element']}{WORDS.get(row['source_action_on_analogy'], row['source_action_on_analogy'])}"
            )
        groups.append(element + "：" + "，".join(relations))
    result["tips"][7] = (
        "任氏另分太旺、旺极、太衰、衰极。按本段逐项保留的四态取用关系为："
        + "；".join(groups)
        + "。“所似”是该段有条件的取用比拟，不改字面五行，也未给出可直接套用的四态数值界限；"
        "未知四态不能由工程三档或人物际遇补造。"
    )
    curation = result["curation"]
    curation["method_id"] = "dtcw1947_body_vocabulary_semantics_v3"
    curation["entry_revision"] = 3
    curation["source_relation_binding"] = {
        "method_id": "dtcw1947_four_state_source_rows_v1",
        "tip_indexes": [7],
        "source_claim_id": reference["claim_id"],
        "source_sha256": reference["source_pdf_sha256"],
        "source_pdf_pages": reference["source_pdf_pages"],
        "source_rows_sha256": digest(source),
        "rows": copy.deepcopy(rows),
        "numeric_classifier_implemented": False,
        "independent_annotation_review": "not_certified",
    }
    curation["revision_correction"] = {
        "supersedes_entry_revision": 2,
        "corrected_relation_keys": ["木/旺極", "木/太衰", "木/衰極"],
        "reason": "修订2的木旺极取用写错，太衰与衰极对应互换；原页与既存全表一致。保留原修订及其工程验收记录。",
    }
    curation["citation"] += (
        " 修订3依据同版PDF177—178的20项关系表纠正木旺极、太衰、衰极三处摘要对应；"
        "全表逐项呈现，不认证数值分类器或独立复核。"
    )
    return old, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    old, expected = expected_card()
    bundle = json.loads(BUNDLE.read_text())
    actual = bundle["categories"][CATEGORY][KEY]
    if args.check:
        if actual != expected:
            print(
                "FAIL: current card differs from the frozen20-row source-bound revision3"
            )
            return 1
        print("PASS: revision3 matches the frozen20-row source-bound rendering")
        return 0
    if actual not in (old, expected):
        raise ValueError("Current target card changed concurrently; do not overwrite")
    bundle["categories"][CATEGORY][KEY] = expected
    BUNDLE.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n")
    print("Updated one knowledge card to source-bound revision3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
