"""Declared receipt paging restores every field; business omissions still fail."""

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

import pytest
from mcp.types import TextResourceContents

from fatebridge.application.tool_spec import ServiceResult
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt, read_full_result

MANIFEST_URI = "fatebridge://results/unit"
PAGE_URI = f"{MANIFEST_URI}/pages/0"


@dataclass(kw_only=True)
class ReceiptPages:
    text: str
    read_count: int = 0

    async def read_resource(self, uri: str) -> list[TextResourceContents]:
        self.read_count += 1
        if uri == MANIFEST_URI:
            envelope = {
                "result_id": "unit",
                "first_page_uri": PAGE_URI,
                "total_chars": len(self.text),
                "run_metadata": json.loads(self.text)["run_metadata"],
            }
        else:
            assert uri == PAGE_URI
            envelope = {
                "result_id": "unit",
                "offset": 0,
                "next_offset": None,
                "text": self.text,
                "next_uri": None,
                "total_chars": len(self.text),
            }
        return [
            TextResourceContents.model_validate(
                {"uri": uri, "text": json.dumps(envelope)}
            )
        ]


@dataclass(kw_only=True)
class ReceiptExample:
    full: dict[str, ServiceResult]
    inline: dict[str, ServiceResult]
    pages: ReceiptPages


def make_receipt_example() -> ReceiptExample:
    full: dict[str, ServiceResult] = {
        "ziwei_birth": {"star": "紫微", "branch": "子"},
        "run_metadata": {
            "run_id": "unit",
            "tool_name": "ziwei_birth",
            "provenance": {"source": "the original source"},
            "determinism": {"scope": "the original scope"},
            "runtime": {"ephemeris": {"files": ["source.se1"]}},
        },
    }
    text = json.dumps(full, ensure_ascii=False, separators=(",", ":"))
    inline = deepcopy(full)
    inline["run_metadata"].pop("provenance")
    inline["run_metadata"].pop("determinism")
    inline["run_metadata"]["runtime"] = {
        "delivery_path": "run_metadata.runtime",
        "ephemeris_files_count": 1,
    }
    inline["result_delivery"] = {
        "mode": "paged",
        "result_id": "unit",
        "manifest_uri": MANIFEST_URI,
        "total_chars": len(text),
        "first_page_uri": PAGE_URI,
        "deferred_fields": [
            "run_metadata.runtime",
            "run_metadata.provenance",
            "run_metadata.determinism",
        ],
    }
    return ReceiptExample(full=full, inline=inline, pages=ReceiptPages(text=text))


@pytest.mark.parametrize("is_compact", [False, True])
def test_explicit_metadata_paging_restores_the_exact_original_receipt(
    is_compact: bool,
) -> None:
    """Restore the full receipt without mutating the inline result."""
    example = make_receipt_example()
    if is_compact:
        example.inline["result_delivery"].pop("first_page_uri")
        example.inline["result_delivery"]["compact_reference"] = True
    else:
        pass
    original_inline = deepcopy(example.inline)
    restored = asyncio.run(verified_inline_business(example.pages, example.inline))
    assert restored == example.full
    assert example.inline == original_inline
    assert example.pages.read_count == 2


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("manifest", "result_id", "different"),
        ("manifest", "total_chars", 0),
        ("manifest", "first_page_uri", "fatebridge://results/different/pages/0"),
        ("page", "result_id", "different"),
        ("page", "total_chars", 0),
        ("page", "offset", 1),
        ("page", "next_offset", 0),
        ("page", "next_uri", PAGE_URI),
    ],
)
def test_original_readback_rejects_mismatched_manifest_and_page_identity(
    target: Literal["manifest", "page"], field: str, value: str | int
) -> None:
    """Reject broken artifact identity or page order before merging any fields."""
    example = make_receipt_example()

    class CorruptPages(ReceiptPages):
        async def read_resource(self, uri: str) -> list[TextResourceContents]:
            response = await super().read_resource(uri)
            if uri == (MANIFEST_URI if target == "manifest" else PAGE_URI):
                envelope: ServiceResult = json.loads(response[0].text)
                envelope[field] = value
                response[0].text = json.dumps(envelope)
            else:
                pass
            return response

    with pytest.raises(AssertionError):
        asyncio.run(
            read_full_result(CorruptPages(text=example.pages.text), example.inline)
        )


@pytest.mark.parametrize(
    "change",
    [
        "missing_declaration",
        "extra_declaration",
        "identity",
        "count",
        "boolean_count",
        "boolean_coercion",
    ],
)
def test_receipt_recovery_requires_exact_declarations_and_essential_identity(
    change: Literal[
        "missing_declaration",
        "extra_declaration",
        "identity",
        "count",
        "boolean_count",
        "boolean_coercion",
    ],
) -> None:
    """Reject mismatched declarations, identity and supplemental field types."""
    example = make_receipt_example()
    receipt = example.inline["run_metadata"]
    full_receipt = example.full["run_metadata"]
    deferred: list[str] = example.inline["result_delivery"]["deferred_fields"]
    assert_same_run_receipt(receipt, full_receipt, deferred_fields=deferred)
    if change == "missing_declaration":
        deferred[:] = ["run_metadata.runtime"]
    elif change == "extra_declaration":
        deferred.append("run_metadata.unused")
    elif change == "identity":
        receipt.pop("run_id")
        deferred.append("run_metadata.run_id")
    elif change == "count":
        receipt["runtime"]["ephemeris_files_count"] = 2
    elif change == "boolean_count":
        receipt["runtime"]["ephemeris_files_count"] = True
    else:
        full_receipt["determinism"]["randomness_used"] = False
        receipt["determinism"] = {
            **full_receipt["determinism"],
            "randomness_used": 0,
        }
        deferred.remove("run_metadata.determinism")
    with pytest.raises(AssertionError):
        assert_same_run_receipt(receipt, full_receipt, deferred_fields=deferred)


@pytest.mark.parametrize(
    "change",
    [
        "business",
        "missing_star",
        "undeclared",
        "forged_provenance",
        "identity",
        "environment",
        "artifact",
        "business_deferral",
        "identity_deferral",
        "duplicate",
    ],
)
def test_receipt_restoration_never_hides_missing_or_changed_facts(
    change: Literal[
        "business",
        "missing_star",
        "undeclared",
        "forged_provenance",
        "identity",
        "environment",
        "artifact",
        "business_deferral",
        "identity_deferral",
        "duplicate",
    ],
) -> None:
    """Reject changed business facts even when the artifact itself is readable."""
    example = make_receipt_example()
    inline = example.inline
    deferred: list[str] = inline["result_delivery"]["deferred_fields"]
    if change == "business":
        inline["ziwei_birth"]["branch"] = "午"
    elif change == "missing_star":
        inline["ziwei_birth"].pop("star")
    elif change == "undeclared":
        deferred.remove("run_metadata.provenance")
    elif change == "forged_provenance":
        inline["run_metadata"]["provenance"] = {"source": "forged"}
    elif change == "identity":
        inline["run_metadata"]["run_id"] = "different"
    elif change == "environment":
        inline["run_metadata"]["runtime"]["ephemeris_files_count"] = 2
    elif change == "artifact":
        example.pages.text = example.pages.text.replace("紫微", "太阳")
    elif change == "business_deferral":
        deferred.append("ziwei_birth")
    elif change == "identity_deferral":
        deferred.append("run_metadata.run_id")
    else:
        deferred.append("run_metadata.provenance")
    with pytest.raises(AssertionError):
        asyncio.run(verified_inline_business(example.pages, inline))
