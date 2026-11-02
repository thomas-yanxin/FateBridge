"""Render source-local editorial knowledge without changing strength policies."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_frontmatter_knowledge_v1"
BUNDLE = ROOT / "src/fatebridge/data/knowledge/bazi-frontmatter.json"
CATEGORY = "source_vocabulary"
PINNED_PROTOCOL = "3cd171eef27321afb8af3702efe02ac32b65d003239fdc24b9cfcc5538d13268"
PINNED_PLAN = "17bcd99ecbf7d73cb643b2e2e4b6bce494369e4e490af81dbeb7c1d527e357e4"
PINNED_CROSS_REFERENCE = (
    "23c5e118d524fa879c50c51959524c36280bd194324de0c1664b966226e77c17"
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(path):
    if sha(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Source-bound editorial input changed: " + path.name)
    return json.loads(path.read_text())


def expected_bundle():
    protocol_path = FIXTURE / "protocol.json"
    protocol = bound(protocol_path)
    if sha(protocol_path) != PINNED_PROTOCOL:
        raise ValueError("Frontmatter review belongs to a different protocol")
    binding_path = FIXTURE / "source-binding.json"
    source = bound(binding_path)
    plan = bound(FIXTURE / "curation-plan.json")
    if sha(FIXTURE / "curation-plan.json") != PINNED_PLAN:
        raise ValueError("Reviewed editorial plan changed, even with a rebound sidecar")
    if sha(binding_path) != protocol["source_binding_sha256"] or plan[
        "source_binding_sha256"
    ] != sha(binding_path):
        raise ValueError("Editorial plan lost the reviewed source binding")
    for path_key, hash_key in [
        ("source_djvu_path", "source_djvu_sha256"),
        ("source_supplement_path", "source_supplement_sha256"),
        ("gap_review_path", "gap_review_sha256"),
    ]:
        if sha(ROOT / source[path_key]) != source[hash_key]:
            raise ValueError("Original source or review bytes changed")
    for path, expected in source["source_images_sha256"].items():
        if sha(ROOT / path) != expected:
            raise ValueError("Original leaf image changed")
    reference = bound(FIXTURE / "cross-reference-binding.json")
    if sha(FIXTURE / "cross-reference-binding.json") != PINNED_CROSS_REFERENCE:
        raise ValueError(
            "Reviewed cross-reference changed, even with a rebound sidecar"
        )
    # The reference binds the original85-entry edition. Later independent
    # cards may be appended, while this actual source-bound card stays exact.
    base_path = (
        ROOT
        / "docs/validation/bazi-body-vocabulary-knowledge-v3/current-workspace/src/fatebridge/data/knowledge/bazi.json"
    )
    if sha(base_path) != reference["base_bundle_sha256"]:
        raise ValueError("Original Ren four-state bundle changed")
    original_card = json.loads(base_path.read_bytes())["categories"][
        "classical_force_semantics"
    ][reference["existing_key"]]
    current_card = json.loads(
        (ROOT / "src/fatebridge/data/knowledge/bazi.json").read_bytes()
    )["categories"]["classical_force_semantics"][reference["existing_key"]]
    if current_card != original_card:
        raise ValueError("Existing Ren four-state card changed")
    rows = source["all30_rows"]
    if (
        len(rows) != 30
        or len({r["id"] for r in rows}) != 30
        or source["explicit_excluded_contexts"] != ["从", "化", "变格"]
        or source["numeric_classifier_implemented"]
    ):
        raise ValueError("Incomplete table or lost source exclusions")
    groups = {
        element: [r for r in rows if r["element"] == element]
        for element in "木火土金水"
    }
    if any(len(group) != 6 for group in groups.values()) or any(
        r["literal_pillars"] is not None
        or r["expected_daymaster_strength"] is not None
        or r["implemented_or_evaluated"]
        or not r["limited_by_candidate_leaf56"]
        for r in rows
    ):
        raise ValueError("Table terms must not acquire chart labels or unscoped rules")
    entries = {}
    for card in plan["cards"]:
        tips = [
            (
                tip
                if isinstance(tip, str)
                else tip["table_element"]
                + "："
                + "；".join(
                    row["normalized_source_text"]
                    for row in groups[tip["table_element"]]
                )
                + "。"
            )
            for tip in card["tips"]
        ]
        indices = sum(
            [
                card[k]
                for k in [
                    "source_tip_indices",
                    "implementation_tip_indices",
                    "editorial_tip_indices",
                ]
            ],
            [],
        )
        if sorted(indices) != list(range(len(tips))):
            raise ValueError("Every tip needs an explicit source or editorial role")
        ref = dict(
            author="李雨田增补（初学捷径；雨田按）",
            title="初學捷徑·衰旺強弱之別／看命三法／五行衰旺取用法",
            container="任注滴天髓闡微，李雨田校訂，上海大東書局1947年4月初版影印资料",
            source_url="https://commons.wikimedia.org/wiki/File:CADAL07005210_滴天髓闡微.djvu",
            catalog_url="https://cadal.edu.cn/cardpage/bookCardPage?ssno=07005210",
            source_kind="additional_digital_witness_single_reader_not_independent_edition",
            source_sha256=source["source_djvu_sha256"],
            source_djvu_leaves=card["leaves"],
            printed_pages=card["printed_pages"],
            tip_indices=card["source_tip_indices"],
            support_scope="本节编者层的概念、组合前提和适用限制；不是任氏正文、原韵文、数值常数或现实效度证明。",
        )
        citation = (
            "FateBridge限域编释及源表编录，非逐字引文；李雨田增补《初学捷径》，"
            "收入《任注滴天髓阐微》；CADAL07005210数字扫描叶"
            + "、".join(map(str, card["leaves"]))
            + "；单读者校读，未完成独立专家审定；"
            + ref["source_url"]
        )
        curation = dict(
            method_id="dtcw1947_li_frontmatter_source_scope_v1",
            entry_revision=1,
            classification="source_local_editorial_vocabulary_and_table_conditions_not_classifier",
            review_status="single_reader_source_scoped_not_full_classical_acceptance",
            source_tip_indices=card["source_tip_indices"],
            implementation_tip_indices=card["implementation_tip_indices"],
            editorial_tip_indices=card["editorial_tip_indices"],
            source_refs=[ref],
            source_binding=dict(
                protocol_sha256=sha(protocol_path),
                reviewed_binding_sha256=sha(binding_path),
                source_supplement_sha256=source["source_supplement_sha256"],
                gap_review_sha256=source["gap_review_sha256"],
                source_leaf_images_sha256={
                    p: h
                    for p, h in source["source_images_sha256"].items()
                    if int(Path(p).stem.split("-")[1]) in card["leaves"]
                },
                original516_source_not_replaced=True,
            ),
            numerical_strength_rules_adopted=False,
            independent_expert_review="not_completed",
            reality_prediction_efficacy="not_tested",
            original26_disagreement_gate_closed=False,
            citation=citation,
        )
        if card["implementation_tip_indices"]:
            curation["implementation_refs"] = [
                dict(
                    source_path="src/fatebridge/core/strength.py",
                    source_sha256=protocol["prechange_hashes"][
                        "src/fatebridge/core/strength.py"
                    ],
                    support_scope="只支持工程模型强、中和、弱三档及系数为工程政策；不为原典四字设立数值定义。",
                )
            ]
        if card["key"] != "得时得势得地的判读对象":
            curation["separate_Ren_passage"] = dict(
                existing_key=reference["existing_key"],
                source_sha256=reference["binding"]["source_sha256"],
                source_pdf_pages=reference["binding"]["source_pdf_pages"],
                source_claim_id=reference["binding"]["source_claim_id"],
                source_rows_sha256=reference["binding"]["source_rows_sha256"],
                no_cross_author_table_merging=True,
            )
        if card["key"] == "五行取用表的适用范围":
            curation["source_table_binding"] = dict(
                rows=copy.deepcopy(rows),
                rendered_tip_indices=list(range(2, 7)),
                exclusion_tip_index=1,
                applies_to_all_rows=["五行正常之理"],
                excluded_contexts=source["explicit_excluded_contexts"],
                numeric_thresholds_defined=False,
                individual_outcome_rules_adopted=False,
            )
        entries[card["key"]] = dict(title=card["key"], tips=tips, curation=curation)
    if list(entries) != protocol["planned_keys"]:
        raise ValueError("Unreviewed editorial card added or removed")
    return dict(
        schema_version=1,
        id="fatebridge_bazi_frontmatter_v1",
        version=1,
        domain="bazi",
        description="李雨田初学捷径的来源术语及正常五行取用条件；保留作者差异、未知阈值和从化变格例外。",
        categories={CATEGORY: entries},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = expected_bundle()
    if args.check:
        if not BUNDLE.exists() or json.loads(BUNDLE.read_text()) != expected:
            print("FAIL: frontmatter supplement differs from frozen source-bound plan")
            return 1
        print(
            "PASS: three source-local cards and all30 table rows match the frozen plan"
        )
        return 0
    if BUNDLE.exists() and json.loads(BUNDLE.read_text()) != expected:
        raise ValueError("Existing frontmatter supplement changed; refuse overwrite")
    BUNDLE.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
    print("Rendered three source-local frontmatter cards; existing knowledge untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
