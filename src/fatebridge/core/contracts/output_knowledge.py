"""Knowledge retrieval and source evidence contracts."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, JsonValue

from fatebridge.core.contracts.output_base import PartialOutput


class KnowledgeCategory(PartialOutput):
    name: str | None = None
    count: int | None = None
    keys: list[str] | None = None
    keys_sample: list[str] | None = None
    supports: list[str] | None = None
    keys_complete: bool | None = None
    key_format: str | None = None
    reference_only: bool | None = None
    coverage: dict[str, JsonValue] | None = None


class KnowledgeCoverage(PartialOutput):
    domain: str | None = None
    categories: list[KnowledgeCategory] | None = None
    missing_categories: list[str] | None = None
    fallback_categories: list[str] | None = None


def _reference_boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("来源参考布尔事实不能用数字或字符串替代。")
    return value


ReferenceTrue = Annotated[Literal[True], BeforeValidator(_reference_boolean)]


ReferenceFalse = Annotated[Literal[False], BeforeValidator(_reference_boolean)]


class KnowledgeSourceRecord(PartialOutput):
    domain: str | None = None
    key: str | None = None
    source_path: str | None = None
    source_kind: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_revision: JsonValue | None = None
    review_status: str | None = None
    scope: str | None = None
    source_witnesses: JsonValue | None = None


class NumerologyKnowledgeDetails(PartialOutput):
    policy_id: Literal["numerology_source_reference_v1"] | None = None
    reference_only: ReferenceTrue | None = None
    personal_applicability_assessed: ReferenceFalse | None = None
    record: dict[str, JsonValue] | None = None


class HumanDesignKnowledgeDetails(PartialOutput):
    policy_id: Literal["human_design_line_reference_v1"] | None = None
    reference_only: ReferenceTrue | None = None
    personal_applicability_assessed: ReferenceFalse | None = None
    record: dict[str, JsonValue] | None = None


class KnowledgeProvenance(PartialOutput):
    source_domain: str | None = None
    domain: str | None = None
    category: str | None = None
    key: str | None = None
    build_timestamp: str | None = None
    upstream_source_marker: str | None = None
    bundle_version: int | None = None
    coverage: KnowledgeCoverage | None = None
    reference_policy_id: (
        Literal["numerology_source_reference_v1", "human_design_line_reference_v1"]
        | None
    ) = None
    source_catalogue_version: int | None = None
    source_records: list[KnowledgeSourceRecord] | None = None
    reference_only: ReferenceTrue | None = None
    personal_applicability_assessed: ReferenceFalse | None = None
    whole_books_collated: ReferenceFalse | None = None
    independent_whole_corpus_review_completed: ReferenceFalse | None = None
    scope: str | None = None


class KnowledgeDomain(PartialOutput):
    domain: str | None = None
    source: str | None = None
    bundle_version: int | None = None
    provenance: KnowledgeProvenance | None = None
    categories: list[KnowledgeCategory] | None = None


class KnowledgeQuery(PartialOutput):
    key: str | None = None
    object_a: str | None = None
    object_b: str | None = None
    jiang_name: str | None = None
    tian_branch: str | None = None
    di_branch: str | None = None


class PlanetInfoSetting(PartialOutput):
    showHouse: int | None = None
    showRuler: int | None = None


class AstroMeaningSetting(PartialOutput):
    enabled: int | None = None


class ExportSettingsTemplate(PartialOutput):
    sections: list[str] | None = None
    planetInfo: PlanetInfoSetting | None = None
    astroMeaning: AstroMeaningSetting | None = None


class ExportTechnique(PartialOutput):
    key: str | None = None
    label: str | None = None
    astro_meaning_title: str | None = None
    astro_meaning_checkbox: str | None = None
    preset_sections: list[str] | None = None
    forbidden_sections: list[str] | None = None
    supports_planet_info: bool | None = None
    supports_astro_meaning: bool | None = None
    supports_hover_meaning: bool | None = None
    planet_info_default: PlanetInfoSetting | None = None
    astro_meaning_default: AstroMeaningSetting | None = None
    settings_template: ExportSettingsTemplate | None = None
