"""Missing optional category is not a licence to accept a different card."""

from copy import deepcopy

import pytest
from pydantic import JsonValue
from typing_extensions import TypedDict

from validation.knowledge_receipts import compare_knowledge_receipt


class FrozenKnowledgeBundle(TypedDict):
    domain: str
    categories: dict[str, dict[str, dict[str, JsonValue]]]


class KnowledgeToolReceipt(TypedDict):
    is_error: bool
    structured_content: dict[str, JsonValue]


class ReceiptComparison(TypedDict):
    receipt_identity_matches: bool
    category_supplied: bool
    failures: list[str]


BUNDLE: FrozenKnowledgeBundle = {
    "domain": "bazi",
    "categories": {"elements": {"木": {}}},
}
SELECTION = {"domain": "bazi", "category": "elements", "key": "木"}
CARD: dict[str, JsonValue] = {
    "title": "木",
    "lines": ["conditioned claim"],
    "source": "frozen source",
    "citation": "revision1",
}
REQUEST = {"domain": "bazi", "key": "木"}
RESULT: KnowledgeToolReceipt = {
    "is_error": False,
    "structured_content": {
        **CARD,
        "run_metadata": {"run_id": "actual", "tool_name": "knowledge_read"},
    },
}


def compare_receipt(
    *,
    bundle: FrozenKnowledgeBundle | None = None,
    arguments: dict[str, str] | None = None,
    result: KnowledgeToolReceipt | None = None,
    actual_run_id: str = "actual",
) -> ReceiptComparison:
    comparison = compare_knowledge_receipt(
        bundle=dict(deepcopy(BUNDLE) if bundle is None else bundle),
        selection=deepcopy(SELECTION),
        arguments=deepcopy(REQUEST) if arguments is None else arguments,
        result=dict(deepcopy(RESULT) if result is None else result),
        expected_card=deepcopy(CARD),
        actual_run_id=actual_run_id,
    )
    return {
        "receipt_identity_matches": comparison["receipt_identity_matches"],
        "category_supplied": comparison["category_supplied"],
        "failures": comparison["failures"],
    }


def test_optional_category_resolves_only_from_the_complete_frozen_bundle() -> None:
    assert compare_receipt()["receipt_identity_matches"]
    explicit = compare_receipt(arguments={**REQUEST, "category": "elements"})
    assert explicit["receipt_identity_matches"]
    assert explicit["category_supplied"]


@pytest.mark.parametrize(
    "changed_argument", [{"domain": "astro"}, {"key": "火"}, {"category": "structures"}]
)
def test_wrong_request_cannot_be_redeemed_by_a_correct_looking_response(
    changed_argument: dict[str, str],
) -> None:
    assert not compare_receipt(arguments={**REQUEST, **changed_argument})[
        "receipt_identity_matches"
    ]


def test_ambiguous_key_cannot_be_resolved_using_the_desired_answer() -> None:
    bundle = deepcopy(BUNDLE)
    bundle["categories"]["other"] = {"木": {}}
    assert not compare_receipt(bundle=bundle)["receipt_identity_matches"]


@pytest.mark.parametrize("field", ["title", "lines", "source", "citation"])
def test_each_returned_card_identity_field_is_checked(field: str) -> None:
    result = deepcopy(RESULT)
    result["structured_content"][field] = "wrong"
    assert "card_mismatch:" + field in compare_receipt(result=result)["failures"]


def test_preparation_run_cannot_substitute_for_the_actual_model_run() -> None:
    assert (
        "actual_run_id_mismatch"
        in compare_receipt(actual_run_id="preparation")["failures"]
    )


def test_error_and_deferred_receipts_are_not_full_successful_cards() -> None:
    assert not compare_receipt(result={**RESULT, "is_error": True})[
        "receipt_identity_matches"
    ]
    result = deepcopy(RESULT)
    result["structured_content"]["result_delivery"] = {"mode": "paged"}
    assert not compare_receipt(result=result)["receipt_identity_matches"]
