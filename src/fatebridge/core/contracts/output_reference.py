"""Stable nested facts, with projection-compatible optional fields.

Validate existing payloads without reserialization; dynamic map keys and
extension fields remain open. Definitions follow the service builders.
"""

from typing import Any

from fatebridge.core.contracts.output_knowledge import (
    HumanDesignKnowledgeDetails,
    KnowledgeDomain,
    KnowledgeProvenance,
    KnowledgeQuery,
    NumerologyKnowledgeDetails,
    ReferenceTrue,
)
from fatebridge.core.contracts.output_sukuyo_relationships import (
    SukuyoCandidateAnalysis,
    SukuyoDay,
    SukuyoPerson,
    SukuyoRelation,
    SuzhanAstronomy,
)

__all__ = [
    "HumanDesignKnowledgeDetails",
    "NumerologyKnowledgeDetails",
    "REFERENCE_TOOL_FIELDS",
    "SukuyoDay",
]


REFERENCE_TOOL_FIELDS: dict[str, dict[str, Any]] = {
    "suzhan": {"sukuyo": SukuyoDay, "astronomy": SuzhanAstronomy},
    "sukuyo_compatibility": {
        "su27_basis": str,
        "status": str,
        "person1": SukuyoPerson,
        "person2": SukuyoPerson,
        "person1_to_person2": SukuyoRelation,
        "person2_to_person1": SukuyoRelation,
        "candidate_relation_analysis": SukuyoCandidateAnalysis,
        "pair": str,
        "summary": str,
    },
    "knowledge_catalog": {
        "domains": list[KnowledgeDomain],
        "provenance": KnowledgeProvenance,
    },
    "knowledge_read": {
        "query_normalized": KnowledgeQuery,
        "provenance": KnowledgeProvenance,
        "lines": list[str],
        "tips": list[str],
        "reference_only": ReferenceTrue,
        "reference_details": NumerologyKnowledgeDetails | HumanDesignKnowledgeDetails,
    },
}
