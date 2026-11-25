"""Ziwei palaces, stars and source evidence."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import BranchName


class ZiweiPosition(BranchName):
    ganzhi: str | None = None


class ZiweiStar(PartialOutput):
    name: str | None = None
    label: str | None = None
    brightness: str | None = None
    mutagen: str | None = None


class ZiweiRelatedPalace(PartialOutput):
    relation: str | None = None
    natal_palace_name: str | None = None
    natal_palace_ganzhi: str | None = None
    branch: str | None = None
    stars_detail: list[ZiweiStar] | None = None


class ZiweiStructuralEvidence(PartialOutput):
    major_stars: list[str] | None = None
    is_empty_main_palace: bool | None = None
    sanfang_sizheng: list[ZiweiRelatedPalace] | None = None
    opposite_stars_relocated: bool | None = None


class ZiweiSihuaSourcePosition(PartialOutput):
    natal_palace_name: str | None = None
    natal_branch: str | None = None
    natal_mutagen: str | None = None
    calculation_path: str | None = None


class ZiweiSihuaSourceDifference(PartialOutput):
    year_stem: str | None = None
    transformation: str | None = None
    selected_star: str | None = None
    compared_star: str | None = None
    selected_position: ZiweiSihuaSourcePosition | None = None
    compared_position: ZiweiSihuaSourcePosition | None = None


class ZiweiSihuaSourceComparison(PartialOutput):
    dynamic_reuse_classically_verified: bool | None = None
    method_id: str | None = None
    version: str | None = None
    compared_source: str | None = None
    source_title: str | None = None
    source_section: str | None = None
    printed_volume: str | None = None
    source_cell_count: int | None = None
    manual_reader_count: int | None = None
    scope: str | None = None
    source_frame: int | None = None
    source_reading: str | None = None
    year_stem: str | None = None
    source_agrees_on_this_stem: bool | None = None
    compared_assignments_applied: bool | None = None
    whole_book_conformance_claimed: bool | None = None
    differences: list[ZiweiSihuaSourceDifference] | None = None


class ZiweiRuleset(PartialOutput):
    sihua_source: str | None = None
    sihua_source_url: str | None = None
    id: str | None = None
    version: str | None = None
    baseline_source: str | None = None
    classical_source: str | None = None
    source_kind: str | None = None
    overrides: list[str] | None = None
    leap_month_rule: str | None = None
    sihua_rule: str | None = None
    target_leap_month_rule: str | None = None
    dynamic_sihua_rule: str | None = None
    brightness_rule: str | None = None
    classical_conformance: str | None = None
    unresolved: list[str] | None = None
    real_world_efficacy: str | None = None


class ZiweiRuleTrace(PartialOutput):
    rule_id: str | None = None
    source: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    outputs: dict[str, OpenJsonValue] | None = None


class ZiweiCycleRules(PartialOutput):
    status: str | None = None
    changsheng_start: str | None = None
    changsheng_direction: str | None = None
    changsheng_rule: str | None = None
    changsheng_source: str | None = None
    boshi_start: str | None = None
    boshi_direction: str | None = None
    boshi_rule: str | None = None
    boshi_source: str | None = None
    label_scope: str | None = None
    naming_note: str | None = None
    missing_gender_resolution: str | None = None
    gender_invariant_positions: dict[str, dict[str, str]] | None = None


class ZiweiCycleSourceHeader(PartialOutput):
    source_start: str | None = None
    actual_start_branches: list[str] | None = None
    reported_start: str | None = None
    start_match: bool | None = None
    source_direction: str | None = None
    actual_direction: str | None = None
    direction_match: bool | None = None


class ZiweiCycleSourcePosition(PartialOutput):
    actual: str | None = None
    candidates: list[str] | None = None
    match: bool | None = None


class ZiweiCycleSourceComparison(PartialOutput):
    method_id: str | None = None
    version: str | None = None
    source: str | None = None
    printed_volume: str | None = None
    source_frames: dict[str, int] | None = None
    inputs: dict[str, str] | None = None
    scope: str | None = None
    changsheng: ZiweiCycleSourceHeader | None = None
    boshi: ZiweiCycleSourceHeader | None = None
    positions: dict[str, dict[str, ZiweiCycleSourcePosition]] | None = None
    source_rule_applied: dict[str, bool] | None = None
    source_name_mapping: dict[str, str] | None = None
    unknown_gender_policy: str | None = None
    manual_reader_count: int | None = None
    whole_book_conformance_claimed: bool | None = None


class ZiweiChartMaster(PartialOutput):
    star: str | None = None
    selection_basis: str | None = None
    basis_branch: str | None = None
    natal_palace_name: str | None = None
    natal_branch: str | None = None
    source: str | None = None
    source_status: str | None = None


class ZiweiChartMasters(PartialOutput):
    life: ZiweiChartMaster | None = None
    body: ZiweiChartMaster | None = None


class ZiweiFlowingStar(PartialOutput):
    star: str | None = None
    scope: str | None = None
    branch: str | None = None
    scope_palace_name: str | None = None
    natal_palace_name: str | None = None
    rule_id: str | None = None
    stem: str | None = None
    source: str | None = None
    natal_stars_relocated: bool | None = None
    system_id: str | None = None
    year_branch: str | None = None


class ZiweiAnnualThreeSha(PartialOutput):
    rule_id: str | None = None
    scope: str | None = None
    year_branch: str | None = None
    names_as_written: list[str] | None = None
    branches: list[str] | None = None
    individual_name_positions: dict[str, str] | None = None
    individual_assignment_status: str | None = None
    source: str | None = None
    distinct_from_boshi_cycle: bool | None = None


class ZiweiSymbolicRecord(PartialOutput):
    star: str | None = None
    source_name: str | None = None
    elements_as_written: list[str] | None = None
    source_quote: str | None = None
    source_section: str | None = None
    natal_palace_name: str | None = None
    natal_branch: str | None = None
    natal_brightness: str | None = None
    natal_mutagen: str | None = None
    calculation_path: str | None = None


class ZiweiSymbolicProperties(PartialOutput):
    method_id: str | None = None
    source: str | None = None
    source_status: str | None = None
    element_collation_source: str | None = None
    element_collation_frames: list[int] | None = None
    element_collation_scope: str | None = None
    scope: str | None = None
    textual_hua_terms_are_sihua: bool | None = None
    multi_element_text_retained: bool | None = None
    records: list[ZiweiSymbolicRecord] | None = None
