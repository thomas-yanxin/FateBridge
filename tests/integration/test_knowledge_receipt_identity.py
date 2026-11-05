"""Missing optional category is not a licence to accept a different card."""

from copy import deepcopy

import pytest

from fatebridge.validation.knowledge_receipts import compare_knowledge_receipt

BUNDLE = {"domain": "bazi", "categories": {"elements": {"木": {}}}}
SELECTION = {"domain": "bazi", "category": "elements", "key": "木"}
CARD = {
    "title": "木",
    "lines": ["conditioned claim"],
    "source": "frozen source",
    "citation": "revision1",
}
REQUEST = {"domain": "bazi", "key": "木"}
RESULT = {
    "is_error": False,
    "structured_content": {
        **CARD,
        "run_metadata": {"run_id": "actual", "tool_name": "knowledge_read"},
    },
}


def compare(**updates):
    inputs = dict(
        bundle=deepcopy(BUNDLE),
        selection=deepcopy(SELECTION),
        arguments=deepcopy(REQUEST),
        result=deepcopy(RESULT),
        expected_card=deepcopy(CARD),
        actual_run_id="actual",
    )
    inputs.update(updates)
    return compare_knowledge_receipt(**inputs)


def test_optional_category_resolves_only_from_the_complete_frozen_bundle():
    assert compare()["receipt_identity_matches"]
    explicit = compare(arguments={**REQUEST, "category": "elements"})
    assert explicit["receipt_identity_matches"]
    assert explicit["category_supplied"]


@pytest.mark.parametrize(
    "update", [{"domain": "astro"}, {"key": "火"}, {"category": "structures"}]
)
def test_wrong_request_cannot_be_redeemed_by_a_correct_looking_response(update):
    assert not compare(arguments={**REQUEST, **update})["receipt_identity_matches"]


def test_ambiguous_key_cannot_be_resolved_using_the_desired_answer():
    bundle = deepcopy(BUNDLE)
    bundle["categories"]["other"] = {"木": {}}
    assert not compare(bundle=bundle)["receipt_identity_matches"]


@pytest.mark.parametrize("field", ["title", "lines", "source", "citation"])
def test_each_returned_card_identity_field_is_checked(field):
    result = deepcopy(RESULT)
    result["structured_content"][field] = "wrong"
    assert "card_mismatch:" + field in compare(result=result)["failures"]


def test_preparation_run_cannot_substitute_for_the_actual_model_run():
    assert "actual_run_id_mismatch" in compare(actual_run_id="preparation")["failures"]


def test_error_and_deferred_receipts_are_not_full_successful_cards():
    assert not compare(result={**RESULT, "is_error": True})["receipt_identity_matches"]
    result = deepcopy(RESULT)
    result["structured_content"]["result_delivery"] = {"mode": "paged"}
    assert not compare(result=result)["receipt_identity_matches"]
