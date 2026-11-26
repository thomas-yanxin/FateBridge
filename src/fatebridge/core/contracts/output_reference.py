"""Stable nested facts, with projection-compatible optional fields.

Validate existing payloads without reserialization; dynamic map keys and
extension fields remain open. Definitions follow the service builders.
"""

from typing import Any

from fatebridge.core.contracts.output_knowledge import (
    AstroMeaningSetting,
    ExportTechnique,
    HumanDesignKnowledgeDetails,
    KnowledgeDomain,
    KnowledgeProvenance,
    KnowledgeQuery,
    NumerologyKnowledgeDetails,
    PlanetInfoSetting,
    ReferenceTrue,
)
from fatebridge.core.contracts.output_snapshot_export import (
    ExportSection,
    NormalizedExportSettings,
    SnapshotExport,
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
    "SnapshotExport",
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
    "knowledge_registry": {
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
    "export_registry": {
        "techniques": list[ExportTechnique],
        "selected_technique": ExportTechnique,
        "planet_info_default": PlanetInfoSetting,
        "astro_meaning_default": AstroMeaningSetting,
        "default_normalized_settings": NormalizedExportSettings,
        "jieqi_split_keys": list[str],
    },
    "export_parse": {
        "technique": ExportTechnique,
        "settings_used": NormalizedExportSettings,
        "sections": list[ExportSection],
        "selected_sections": list[str],
        "section_titles_detected": list[str],
        "unknown_detected_sections": list[str],
        "missing_selected_sections": list[str],
    },
}
