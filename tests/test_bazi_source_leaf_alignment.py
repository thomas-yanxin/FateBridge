"""Check a layout aid against exhaustive paths, never against model labels."""

import copy
import gzip
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "source_leaf_alignment", ROOT / "scripts/align_bazi_source_leaves.py"
)
alignment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alignment)


def exhaustive_costs(matrix, gap, n, m, i=0, j=0):
    # Enumerate complete edit sequences, independently of the dynamic program.
    if i == n and j == m:
        yield 0
    if i < n:
        for suffix in exhaustive_costs(matrix, gap, n, m, i + 1, j):
            yield gap + suffix
    if j < m:
        for suffix in exhaustive_costs(matrix, gap, n, m, i, j + 1):
            yield gap + suffix
    if i < n and j < m:
        for suffix in exhaustive_costs(matrix, gap, n, m, i + 1, j + 1):
            yield matrix[i][j] + suffix


def test_optimum_matches_exhaustive_edit_sequences():
    for n, m in itertools.product(range(3), repeat=2):
        for flat in itertools.product((0, 0.25, 1), repeat=n * m):
            matrix = [list(flat[i * m : (i + 1) * m]) for i in range(n)]
            for gap in (0.05, 0.1, 0.2, 0.4):
                result = alignment.align(matrix, gap, new_count=m)
                assert result["total_layout_cost"] == pytest.approx(
                    min(exhaustive_costs(matrix, gap, n, m))
                )
                rows = result["rows"]
                for key, count in [("original", n), ("candidate", m)]:
                    assert [r[key] for r in rows if r[key] is not None] == list(
                        range(1, count + 1)
                    )
                reconstructed = sum(r.get("image_distance", gap) for r in rows)
                assert reconstructed == pytest.approx(result["total_layout_cost"])
                assert not result["semantic_equality_certified"]


def test_inserted_and_deleted_leaves_are_retained_without_offset_repair():
    matrix = [[0, 1, 1, 1], [1, 1, 0, 1], [1, 1, 1, 1]]
    rows = alignment.align(matrix, 0.1)["rows"]
    assert {
        (r["original"], r["candidate"]) for r in rows if r["action"] == "match"
    } == {(1, 1), (2, 3)}
    assert {r["candidate"] for r in rows if r["action"] == "candidate_only"} == {2, 4}
    assert [r["original"] for r in rows if r["action"] == "original_only"] == [3]


def test_duplicate_blank_descriptors_do_not_become_text_certification():
    costs = alignment.distances(
        [{"vector": [0, 0]}, {"vector": [0, 0]}],
        [{"vector": [0, 0]}, {"vector": [0, 0]}, {"vector": [0, 0]}],
    )
    result = alignment.align(costs, 0.1)
    assert result["total_layout_cost"] == pytest.approx(0.1)
    assert len(result["rows"]) == 3
    assert not result["semantic_equality_certified"]
    assert all(r["status"] != "text_certified" for r in result["rows"])


@pytest.mark.parametrize("gap", [True, 0, -1, math.nan, math.inf, "0.1"])
def test_invalid_gap_cost_is_rejected(gap):
    with pytest.raises(ValueError):
        alignment.align([[0]], gap)


@pytest.mark.parametrize(
    "matrix,count",
    [
        ([[0], []], None),
        ([[math.nan]], None),
        ([[1.1]], None),
        ([[-0.1]], None),
        ([[True]], None),
        ([[0]], True),
        ([[0]], 2),
        ([], -1),
    ],
)
def test_invalid_matrix_or_inventory_is_rejected(matrix, count):
    with pytest.raises(ValueError):
        alignment.align(matrix, 0.1, new_count=count)


@pytest.mark.parametrize("vector", [[], [-1, 0], [math.nan, 0], [1, 1], [True, 0]])
def test_invalid_image_descriptors_are_rejected(vector):
    with pytest.raises(ValueError):
        alignment.distances([{"vector": vector}], [{"vector": [1, 0]}])


def test_orthogonal_and_identical_descriptors_have_expected_distances():
    assert alignment.distances(
        [{"vector": [1, 0]}], [{"vector": [1, 0]}, {"vector": [0, 1]}]
    )[0] == pytest.approx([0, 1])


@pytest.mark.parametrize(
    "attack", ["features", "spec", "source", "inventory", "image", "escape"]
)
def test_forged_alignment_inputs_cannot_hide_missing_or_unbound_leaves(
    tmp_path, attack
):
    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return path

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    image = tmp_path / "image.pgm"
    image.write_bytes(b"P5\n1 1\n255\n\xff")
    source = tmp_path / "source"
    source.write_bytes(b"synthetic input binding, not a classical source")
    spec_path = write("feature-spec-before-first.json", {"gap_cost_profiles": [0.1]})
    data = {
        side: [
            dict(page=i, path="image.pgm", sha256=sha(image), vector=[1, 0])
            for i in range(1, count + 1)
        ]
        for side, count in [("original", 516), ("candidate", 521)]
    }
    if attack == "inventory":
        data["candidate"].pop(51)
    if attack == "escape":
        outside = tmp_path.parent / (tmp_path.name + "-outside.pgm")
        outside.write_bytes(image.read_bytes())
        data["original"][0]["path"] = str(outside)
    feature_path = tmp_path / "features-first.json.gz"
    feature_path.write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
    write(
        "feature-extraction-first.json",
        dict(features_sha256=sha(feature_path), feature_spec_sha256=sha(spec_path)),
    )
    write(
        "protocol-first.json",
        {
            k: dict(path="source", sha256=sha(source))
            for k in ["old_source", "new_source"]
        },
    )
    if attack in {"features", "spec", "source", "image"}:
        target = {
            "features": feature_path,
            "spec": spec_path,
            "source": source,
            "image": image,
        }[attack]
        target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(ValueError):
        alignment.run(tmp_path, tmp_path)


def test_additional_witness_never_changes_original_cases_claims_or_warnings():
    study = ROOT / "docs/validation/bazi-source-leaf-alignment-v1"
    spec = importlib.util.spec_from_file_location(
        "source_leaf_census", ROOT / "scripts/audit_bazi_wholebook_census.py"
    )
    census = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(census)
    before = census.read_bound(study / "census-before-first.json")
    after = census.audit(ROOT / "docs/validation/bazi-ditian-wholebook-census-v1", ROOT)
    formula_path = (
        ROOT
        / "tests/fixtures/bazi_grouped_formula_positions_v1/expected-fields-first.json"
    )
    assert (
        census.sha(formula_path)
        == "e9bdfad8fdbfc0a01dba1d2277103a446b167b6106b2ba5f5f8913d89b2e16aa"
    )
    formulas = json.loads(formula_path.read_text())
    expected = copy.deepcopy(before)
    for case in expected["resolved_source_cases"]:
        case.update(formulas["case_patches"].get(case["case_id"], {}))
    for identity, patch in formulas["claim_patches"].items():
        expected["resolved_source_claims"][identity].update(patch)
    for key in [
        "batches_sha256",
        "resolved_source_cases",
        "resolved_source_claims",
        "transcription_warnings_retained",
        "remaining_transcription_warnings",
        "source_case_input_questions_retained",
        "remaining_case_input_questions",
    ]:
        assert after[key] == expected[key]
    assert len(after["resolved_source_cases"]) == 558
    assert len(after["resolved_source_claims"]) == 1380
    # The later C488 erratum adds one review qualification without changing
    # any source record. Bind both additions exactly, retaining the old map.
    assert after["context_documents_sha256"] == {
        **before["context_documents_sha256"],
        "source-context-leaf-alignment-first.json": (
            "5cab2cf3870aa47bcd53396d6712b6a50890f51f0d8e94a951c0c96826d1bee7"
        ),
        "source-context-c488-review-domain-erratum-first.json": (
            "ba8d9d119b339e27e753e69314726524e4a38e2d71b91e951b88de9d468f019c"
        ),
    }
    assert (
        after["source_qualifications_retained"]
        == before["source_qualifications_retained"] + 2
    )
    assert not after["whole_book_collection_frozen"]
    assert not after["candidate_evaluation_allowed"]
    for name, expected in census.read_bound(
        study / "source-indices-before-first.json"
    ).items():
        assert (
            census.sha(ROOT / "docs/validation/bazi-ditian-wholebook-census-v1" / name)
            == expected
        )


def test_manual_review_covers_every_gap_across_all_predeclared_paths():
    study = ROOT / "docs/validation/bazi-source-leaf-alignment-v1"
    result = json.loads((study / "alignment-first.json").read_text())
    review = json.loads((study / "gap-union-manual-review-first.json").read_text())
    assert [p["gap_cost"] for p in result["paths"]] == [0.05, 0.1, 0.2, 0.4]
    gaps = {side: set() for side in ["original", "candidate"]}
    for path in result["paths"]:
        assert not path["semantic_equality_certified"]
        for row in path["rows"]:
            if row["action"] != "match":
                for side in gaps:
                    if row[side] is not None:
                        gaps[side].add(row[side])
    paired = review["cost_sensitive_pairs"]
    assert gaps["original"] == {r["original"] for r in paired} | {
        r["original_page"] for r in review["original_tail"]
    }
    assert gaps["candidate"] == {r["candidate"] for r in paired} | {
        r["candidate_leaf"] for r in review["candidate_only_block"]
    }
    assert not review["original516_census_replaced"]
    assert review["source_labels_changed"] == 0
    assert review["original26_disagreements_closed"] == 0


def test_frontmatter_source_supplement_keeps_author_and_exception_binding():
    study = ROOT / "docs/validation/bazi-source-leaf-alignment-v1"
    review = json.loads((study / "gap-union-manual-review-first.json").read_text())
    supplement = json.loads(
        (study / "missing-frontmatter-source-supplement-first.json").read_text()
    )
    assert supplement["review_sha256"] == alignment.sha(
        study / "gap-union-manual-review-first.json"
    )
    for row in review["candidate_only_block"]:
        assert alignment.sha(ROOT / row["image"]) == row["image_sha256"]
    assert [r["candidate_leaf"] for r in review["candidate_only_block"]] == list(
        range(51, 59)
    )
    rows = supplement["element_table_rows"]
    assert len(rows) == 30 and len({r["id"] for r in rows}) == 30
    assert all(
        r["literal_pillars"] is None and r["expected_daymaster_strength"] is None
        for r in rows
    )
    assert all(
        r["limited_by_candidate_leaf56"] and not r["implemented_or_evaluated"]
        for r in rows
    )
    assert all(r["source_text_layer"] == "Li_introductory_supplement" for r in rows)
    assert supplement["continuation_reading"][-1]["excluded_contexts"] == [
        "从",
        "化",
        "变格",
    ]
    assert not supplement["force_comparison_allowed"]
