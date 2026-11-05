"""Versioned software disclosures, separate from the original-book identity.

Current execution binds its receipt and text to one published rendering.
The disclosure does not certify a whole book, historical clock or prediction.
"""

from hashlib import sha256
from types import MappingProxyType
from typing import Any, Literal, Mapping

ScopeRevision = Literal["clock_context_separate_v2"]
SCOPE_RENDERING_POLICY_ID = "canping_scope_rendering_v1"
SCOPE_RENDERING_LAYER = "software_explanatory_scope"
CURRENT_SCOPE_REVISION: ScopeRevision = "clock_context_separate_v2"
_STATEMENTS: Mapping[ScopeRevision, str] = MappingProxyType(
    {
        "clock_context_separate_v2": (
            "所列为已单次目读的局部原句，未完成全书及独立复核；"
            "显示分辨率不提升出生记录精度，也不证明现实预测效验。"
        ),
    }
)
CURRENT_SCOPE_STATEMENT = _STATEMENTS[CURRENT_SCOPE_REVISION]


def registered_scope_statements() -> tuple[str, ...]:
    return tuple(_STATEMENTS.values())


def registered_scope_digests() -> tuple[str, ...]:
    return tuple(
        sha256(text.encode("utf-8")).hexdigest() for text in _STATEMENTS.values()
    )


def scope_rendering_receipt(
    revision: ScopeRevision = CURRENT_SCOPE_REVISION,
) -> dict[str, str]:
    """Return detached provenance for one known software text revision."""
    return {
        "policy_id": SCOPE_RENDERING_POLICY_ID,
        "revision": revision,
        "text_sha256": sha256(_STATEMENTS[revision].encode("utf-8")).hexdigest(),
        "layer": SCOPE_RENDERING_LAYER,
    }


def scope_statement_matches_receipt(text: str, receipt: dict[str, str | None]) -> bool:
    """Check supplied facts without inferring or inserting missing fields."""
    for revision, statement in _STATEMENTS.items():
        if text == statement:
            expected = scope_rendering_receipt(revision)
            return all(
                value is None or expected.get(key) == value
                for key, value in receipt.items()
            )
    return False


def scope_rendering_schema() -> dict[str, Any]:
    """Publish the same revision/digest relation for JSON Schema readers."""
    return {
        "allOf": [
            {
                "if": {
                    "required": ["revision"],
                    "properties": {"revision": {"const": revision}},
                },
                "then": {
                    "properties": {
                        "text_sha256": {
                            "enum": [
                                scope_rendering_receipt(revision)["text_sha256"],
                                None,
                            ]
                        }
                    }
                },
            }
            for revision in _STATEMENTS
        ]
    }


def scope_statement_schema() -> dict[str, Any]:
    """Bind supplied text to supplied metadata while allowing projections."""
    return {
        "allOf": [
            {
                "if": {
                    "required": ["scope_statement"],
                    "properties": {"scope_statement": {"const": text}},
                },
                "then": {
                    "properties": {
                        "scope_rendering": {
                            "properties": {
                                "revision": {"enum": [revision, None]},
                                "text_sha256": {
                                    "enum": [
                                        scope_rendering_receipt(revision)[
                                            "text_sha256"
                                        ],
                                        None,
                                    ]
                                },
                            }
                        }
                    }
                },
            }
            for revision, text in _STATEMENTS.items()
        ]
    }
