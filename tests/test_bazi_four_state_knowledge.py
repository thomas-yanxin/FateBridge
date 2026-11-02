"""Source relationships must agree, rather than merely sharing transport bytes."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_body_vocabulary_knowledge_v3"
BUNDLE = Path("src/fatebridge/data/knowledge/bazi.json")
CATEGORY = "classical_force_semantics"
KEY = "日元强弱与性情措辞"
NORMAL = {"旺極": "旺极", "衰極": "衰极", "煉": "炼", "剋": "克", "濟": "济"}


def read(path):
    return json.loads(path.read_text())


def card(path):
    return read(path)["categories"][CATEGORY][KEY]


def reference_rows():
    source = FIXTURE / "source-relations.json"
    protocol = read(FIXTURE / "protocol.json")
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == protocol["frozen20_relation_reference_sha256"]
    )
    return read(source)["rows"]


def source_tuples():
    return {
        (row["element"], NORMAL.get(row["source_state"], row["source_state"])): (
            row["analogous_element"],
            row["preferred_element"],
            NORMAL.get(
                row["source_action_on_analogy"], row["source_action_on_analogy"]
            ),
        )
        for row in reference_rows()
    }


def rendered_tuples(tip):
    if "仅以木为例，依次说" in tip:
        text = tip.split("依次说", 1)[1].split("。", 1)[0]
        matches = [re.fullmatch("似(.)喜(.)(.)", part) for part in text.split("、")]
        assert all(matches) and len(matches) == 4
        return {
            ("木", state): match.groups()
            for state, match in zip(
                ["太旺", "旺极", "太衰", "衰极"], matches, strict=True
            )
        }
    text = tip.split("四态取用关系为：", 1)[1].split("。", 1)[0]
    found = {}
    for group in text.split("；"):
        element, rest = group.split("：", 1)
        for part in rest.split("，"):
            match = re.fullmatch("(太旺|旺极|太衰|衰极)似(.)宜(.)(.)", part)
            assert match, part
            state, analogy, preferred, action = match.groups()
            assert (element, state) not in found
            found[element, state] = (analogy, preferred, action)
    return found


def test_current_card_wood_relationships_match_frozen_source():
    actual = rendered_tuples(card(ROOT / BUNDLE)["tips"][7])
    assert {k: v for k, v in actual.items() if k[0] == "木"} == {
        k: v for k, v in source_tuples().items() if k[0] == "木"
    }


def test_original_revision2_three_wrong_relations_are_preserved_as_failures():
    before = card(FIXTURE / "before" / BUNDLE)
    assert before["curation"]["entry_revision"] == 2
    actual = rendered_tuples(before["tips"][7])
    mismatches = {k for k, v in actual.items() if source_tuples()[k] != v}
    assert mismatches == {("木", "旺极"), ("木", "太衰"), ("木", "衰极")}
    assert actual["木", "太旺"] == source_tuples()["木", "太旺"]


def test_all20_rendered_relations_and_structured_provenance_match_source():
    current = card(ROOT / BUNDLE)
    assert len(source_tuples()) == 20
    assert rendered_tuples(current["tips"][7]) == source_tuples()
    binding = current["curation"]["source_relation_binding"]
    assert binding["rows"] == reference_rows()
    assert binding["source_claim_id"] == "CENSUS-R539"
    assert binding["source_pdf_pages"] == [177, 178]
    assert binding["numeric_classifier_implemented"] is False
    assert binding["independent_annotation_review"] == "not_certified"
    assert all(row["numeric_threshold"] is None for row in binding["rows"])
    assert current["curation"]["entry_revision"] == 3


def test_reference_remains_bound_to_original_transcription_and_source_bytes():
    reference = read(FIXTURE / "source-relations.json")
    source = ROOT / reference["source_batch"]
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == reference["source_batch_sha256"]
    )
    batch = read(source)
    claims = [c for page in batch["pages"] for c in page["technical_rule_claims"]]
    claim = next(c for c in claims if c["claim_id"] == reference["claim_id"])
    assert claim["literal_table_or_relation_data"] == reference_rows()
    pdf = ROOT / "docs/validation/bazi-controller-root-load-v1/source-whole.pdf"
    assert (
        hashlib.sha256(pdf.read_bytes()).hexdigest() == reference["source_pdf_sha256"]
    )
    protocol = read(FIXTURE / "protocol.json")
    for relative, digest in protocol["source_page_images_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest


def test_original_one_card_migration_and_all84_other_cards_remain_exact():
    edition = (
        ROOT
        / "docs/validation/bazi-body-vocabulary-knowledge-v3/current-workspace/src/fatebridge/data/knowledge/bazi.json"
    )
    assert (
        hashlib.sha256(edition.read_bytes()).hexdigest()
        == "d1e2dd29aebd5224a1516de1d2e53bd5e692e917a39171b93f051ecce0237767"
    )
    assert card(ROOT / BUNDLE) == card(edition)
    old, new = read(FIXTURE / "before" / BUNDLE), read(edition)
    assert {k: v for k, v in old.items() if k != "categories"} == {
        k: v for k, v in new.items() if k != "categories"
    }
    changed = []
    for category, entries in old["categories"].items():
        assert set(entries) == set(new["categories"][category])
        for key, entry in entries.items():
            if entry != new["categories"][category][key]:
                changed.append((category, key))
    assert changed == [(CATEGORY, KEY)]
    assert (
        card(FIXTURE / "before" / BUNDLE)["tips"][:7] == card(ROOT / BUNDLE)["tips"][:7]
    )
    assert sum(map(len, new["categories"].values())) == 85


def test_source_bound_builder_check_is_executable_and_does_not_modify_bundle():
    before = (ROOT / BUNDLE).read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_bazi_four_state_knowledge.py"),
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (ROOT / BUNDLE).read_bytes() == before
