"""No sentence, first failed grade, or actual run may be silently substituted."""

import json

import pytest

from scripts.audit_bazi_semantic_review import ROOT, audit

FIRST = ROOT / "docs/validation/bazi-semantic-first-review-v1.json"
CURRENT = ROOT / "docs/validation/bazi-semantic-first-review-v2.json"


def test_first_review_bad_path_is_retained_and_fails_before_the_separate_correction():
    with pytest.raises(ValueError, match="study_stars_profile"):
        audit(FIRST)
    result = audit(CURRENT)
    assert result["cases"] == 11 and result["actual_receipts"] == 10
    assert result["sentence_and_table_units"] == 204
    assert not result["automatic_semantic_acceptance"]


@pytest.mark.parametrize("change", ["quote", "run", "grade", "drop", "bool_as_int"])
def test_wrong_quote_other_run_disappearing_failure_and_skipped_answer_are_rejected(
    change, tmp_path
):
    review = json.loads(CURRENT.read_text())
    first = review["cases"][0]
    if change == "quote":
        first["sentence_and_table_row_reviews"][0]["quote"] = "改写为身强"
    elif change == "run":
        first["source_packets"][0]["run_id"] = "another-run"
    elif change == "grade":
        first["mechanical_checks_passed"] = True
    elif change == "bool_as_int":
        first["source_packets"][0]["actual_projected_payload"]["run_metadata"][
            "engine_is_approximate"
        ] = 1
    else:
        first["sentence_and_table_row_reviews"].pop(0)
    path = tmp_path / "bad-review.json"
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        audit(path)
