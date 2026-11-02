"""Reviewers cannot replace failed runs or cite unread deferred-file fields."""

import json
import shutil
from hashlib import sha256
from pathlib import Path

import pytest

from scripts.audit_bazi_semantic_batch import audit

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "version,review,packets,units",
    [
        (2, "bazi-semantic-repair-review-v1.json", 12, 186),
        (3, "bazi-semantic-readiness-review-v2.json", 16, 194),
    ],
)
def test_all_original_answers_and_actual_receipts_remain_verifiable(
    version, review, packets, units
):
    result = audit(
        ROOT / f"tests/fixtures/bazi_semantic_run_v{version}",
        ROOT / "docs/validation" / review,
    )
    assert result["cases"] == 11
    assert result["actual_receipt_packets"] == packets
    assert result["sentence_units"] == units
    assert result["reality_prediction_efficacy"] == "not_tested"
    assert result["complete_business_hash_verification_claimed"] is False


@pytest.fixture
def review_copy(tmp_path):
    folder = tmp_path / "run"
    shutil.copytree(ROOT / "tests/fixtures/bazi_semantic_run_v3", folder)
    review = json.loads(
        (ROOT / "docs/validation/bazi-semantic-readiness-review-v2.json").read_text()
    )
    path = tmp_path / "review.json"
    return folder, review, path


def test_review_cannot_use_a_real_but_unread_field(review_copy):
    folder, review, path = review_copy
    case = next(c for c in review["cases"] if c["id"] == "bazi_marriage_fidelity")
    # The reviewer has this full field; the model read only three selected keys.
    case["sentence_reviews"][0]["evidence_paths"] = [
        {"packet": 0, "path": "marriage_analysis.evidence_chain.strength_context"}
    ]
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="model did not read"):
        audit(folder, path)


def test_claiming_a_projection_is_full_business_hash_verification_fails(review_copy):
    folder, review, path = review_copy
    case = review["cases"][0]
    packet_file = folder / case["id"] / "review-payloads.json"
    packets = json.loads(packet_file.read_text())
    packets[0]["complete_business_hash_verified"] = True
    packet_file.write_text(json.dumps(packets))
    case["review_payloads_sha256"] = sha256(packet_file.read_bytes()).hexdigest()
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="complete business hash"):
        audit(folder, path)


def test_original_broad_index_is_retained_and_now_rejected():
    with pytest.raises(ValueError, match="Selective read needs actual stdout"):
        audit(
            ROOT / "tests/fixtures/bazi_semantic_run_v3",
            ROOT / "docs/validation/bazi-semantic-readiness-review-v1.json",
        )
