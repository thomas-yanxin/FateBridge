"""Typed, projection-safe Taiyi gate frames and determinate-count evidence."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_taiyi_day import TaiyiSourceComparison


class TaiyiGateCounter(PartialOutput):
    remaining_units_after_current: int | None = None
    source_modulus: int | None = None
    accumulation: int | None = None
    cycle_length: int | None = None
    cycle_unit: str | None = None
    cycle_position: int | None = None
    units_per_gate: int | None = None
    gate_index: int | None = None
    unit_in_gate: int | None = None
    duty_gate: str | None = None
    epoch_basis: str | None = None


class TaiyiGateRow(PartialOutput):
    number: int | None = None
    palace: str | None = None
    door: str | None = None
    spirit_positions: list[str] | None = None


class TaiyiGateCheck(PartialOutput):
    label: str | None = None
    source_path: str | None = None
    position: str | None = None
    sector_number: int | None = None
    door: str | None = None
    gate_source_path: str | None = None
    obstructs: bool | None = None
    incomplete_kind: str | None = None


class TaiyiGateAssessment(PartialOutput):
    status: str | None = None
    reason: str | None = None
    conditions_satisfied: bool | None = None
    checks: list[TaiyiGateCheck] | None = None
    frame_source_path: str | None = None
    source: str | None = None


class TaiyiGateFrame(PartialOutput):
    source_path: str | None = None
    status: str | None = None
    reason: str | None = None
    anchor_number: int | None = None
    anchor_palace: str | None = None
    anchor_source_path: str | None = None
    anchor_source_value: str | int | None = None
    duty_gate: str | None = None
    rows: list[TaiyiGateRow] | None = None
    three_gates: TaiyiGateAssessment | None = None


class TaiyiGateRuleset(PartialOutput):
    sector_rule_id: str | None = None
    sector_sources: list[str] | None = None
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    sources: list[str] | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None
    open_issues: list[str] | None = None


class TaiyiGates(PartialOutput):
    source_comparisons: list[TaiyiSourceComparison] | None = None
    source_counter_alternatives: list[TaiyiGateCounter] | None = None
    source_comparison_source: str | None = None
    source_comparison_scope: str | None = None
    status: str | None = None
    reason: str | None = None
    ruleset: TaiyiGateRuleset | None = None
    calculation_mode: str | None = None
    selected_profile: str | None = None
    scope: str | None = None
    counter: TaiyiGateCounter | None = None
    moving_frame: TaiyiGateFrame | None = None
    old_open_frames: dict[str, TaiyiGateFrame] | None = None
    old_open_summary: dict[str, TaiyiGateFrame] | None = None
    dingmu_comparison_frame: TaiyiGateFrame | None = None
    dingmu_comparison_source: str | None = None


class TaiyiDeterminateStep(PartialOutput):
    palace: str | None = None
    value: int | None = None
    kind: str | None = None


class TaiyiDeterminateTrace(PartialOutput):
    count: int | None = None
    path: list[TaiyiDeterminateStep] | None = None
    terminal_palace: str | None = None
    terminal_excluded: bool | None = None
    counting_rule: str | None = None
    source: str | None = None


class TaiyiDeterminateRotation(PartialOutput):
    ruler_branch: str | None = None
    hegod: str | None = None
    wenchang: str | None = None
    forward_steps: int | None = None


class TaiyiDeterminateSourceDifference(PartialOutput):
    field: str | None = None
    source_value: int | None = None
    rule_derived_value: int | None = None


class TaiyiDeterminate(PartialOutput):
    source_disagreements: list[TaiyiDeterminateSourceDifference] | None = None
    source_comparison_source: str | None = None
    source_comparison_scope: str | None = None
    status: str | None = None
    reason: str | None = None
    marker: str | None = None
    count: int | None = None
    general: int | None = None
    vice_general: int | None = None
    rotation: TaiyiDeterminateRotation | None = None
    source: str | None = None
    scope: str | None = None
