"""Typed, projection-safe Taiyi gate frames and determinate-count evidence."""

from typing import Dict, List, Optional, Union

from .output_base import PartialOutput
from .output_taiyi_day import TaiyiSourceComparison


class TaiyiGateCounter(PartialOutput):
    remaining_units_after_current: Optional[int] = None
    source_modulus: Optional[int] = None
    accumulation: Optional[int] = None
    cycle_length: Optional[int] = None
    cycle_unit: Optional[str] = None
    cycle_position: Optional[int] = None
    units_per_gate: Optional[int] = None
    gate_index: Optional[int] = None
    unit_in_gate: Optional[int] = None
    duty_gate: Optional[str] = None
    epoch_basis: Optional[str] = None


class TaiyiGateRow(PartialOutput):
    number: Optional[int] = None
    palace: Optional[str] = None
    door: Optional[str] = None
    spirit_positions: Optional[List[str]] = None


class TaiyiGateCheck(PartialOutput):
    label: Optional[str] = None
    source_path: Optional[str] = None
    position: Optional[str] = None
    sector_number: Optional[int] = None
    door: Optional[str] = None
    gate_source_path: Optional[str] = None
    obstructs: Optional[bool] = None
    incomplete_kind: Optional[str] = None


class TaiyiGateAssessment(PartialOutput):
    status: Optional[str] = None
    reason: Optional[str] = None
    conditions_satisfied: Optional[bool] = None
    checks: Optional[List[TaiyiGateCheck]] = None
    frame_source_path: Optional[str] = None
    source: Optional[str] = None


class TaiyiGateFrame(PartialOutput):
    source_path: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    anchor_number: Optional[int] = None
    anchor_palace: Optional[str] = None
    anchor_source_path: Optional[str] = None
    anchor_source_value: Optional[Union[str, int]] = None
    duty_gate: Optional[str] = None
    rows: Optional[List[TaiyiGateRow]] = None
    three_gates: Optional[TaiyiGateAssessment] = None


class TaiyiGateRuleset(PartialOutput):
    sector_rule_id: Optional[str] = None
    sector_sources: Optional[List[str]] = None
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    sources: Optional[List[str]] = None
    classical_conformance: Optional[str] = None
    classical_acceptance_passed: Optional[bool] = None
    open_issues: Optional[List[str]] = None


class TaiyiGates(PartialOutput):
    source_comparisons: Optional[List[TaiyiSourceComparison]] = None
    source_counter_alternatives: Optional[List[TaiyiGateCounter]] = None
    source_comparison_source: Optional[str] = None
    source_comparison_scope: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    ruleset: Optional[TaiyiGateRuleset] = None
    calculation_mode: Optional[str] = None
    selected_profile: Optional[str] = None
    scope: Optional[str] = None
    counter: Optional[TaiyiGateCounter] = None
    moving_frame: Optional[TaiyiGateFrame] = None
    old_open_frames: Optional[Dict[str, TaiyiGateFrame]] = None
    old_open_summary: Optional[Dict[str, TaiyiGateFrame]] = None
    dingmu_comparison_frame: Optional[TaiyiGateFrame] = None
    dingmu_comparison_source: Optional[str] = None


class TaiyiDeterminateStep(PartialOutput):
    palace: Optional[str] = None
    value: Optional[int] = None
    kind: Optional[str] = None


class TaiyiDeterminateTrace(PartialOutput):
    count: Optional[int] = None
    path: Optional[List[TaiyiDeterminateStep]] = None
    terminal_palace: Optional[str] = None
    terminal_excluded: Optional[bool] = None
    counting_rule: Optional[str] = None
    source: Optional[str] = None


class TaiyiDeterminateRotation(PartialOutput):
    ruler_branch: Optional[str] = None
    hegod: Optional[str] = None
    wenchang: Optional[str] = None
    forward_steps: Optional[int] = None


class TaiyiDeterminateSourceDifference(PartialOutput):
    field: Optional[str] = None
    source_value: Optional[int] = None
    rule_derived_value: Optional[int] = None


class TaiyiDeterminate(PartialOutput):
    source_disagreements: Optional[List[TaiyiDeterminateSourceDifference]] = None
    source_comparison_source: Optional[str] = None
    source_comparison_scope: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    marker: Optional[str] = None
    count: Optional[int] = None
    general: Optional[int] = None
    vice_general: Optional[int] = None
    trace: Optional[TaiyiDeterminateTrace] = None
    rotation: Optional[TaiyiDeterminateRotation] = None
    source: Optional[str] = None
    scope: Optional[str] = None
