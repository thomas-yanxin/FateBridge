"""Conditional literal-label location, kept separate from original grid cells.

The caller must name the unadjudicated marker-segment hypothesis. It locates
labels without target-based ranking, column shifts, zero for 初, coordinates,
or a natal degree. The original queries retain their unknown mansion context.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, MANSIONS
from fatebridge.core.guolao_nijl_grid import (
    compare_intro_examples,
    load_nijl_grid,
)

DATA = Path(__file__).resolve().parents[1] / "data/guolao/table-usage-v1.json"
DATA_SHA256 = "48b7b99fc74341a089905c2cfcf7d31293051868ad8934696dea17da8997d238"
POLICY = "nijl_preceding_marker_segment_hypothesis_v1"


def _data() -> dict[str, Any]:
    raw = DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATA_SHA256:
        raise ValueError("原页用法资料指纹变化，不能静默改写假设或校注")
    data: dict[str, Any] = json.loads(raw)
    grid = load_nijl_grid()
    if (
        data["context_policy_id"] != POLICY
        or data["source_grid_id"] != grid.source_id
        or data["source_grid_data_sha256"] != grid.data_sha256
        or data["source_grid_image_sha256"] != grid.source_image_sha256
    ):
        raise ValueError("用法审计须绑定同一NIJL原表，不跨见证拼表")
    return data


def _require_policy(policy: str) -> None:
    if policy != POLICY:
        raise ValueError("须明确选择具名的宿标区段假设；不默认继承普通格宿名")


def _label(cell: dict[str, Any]) -> int | str:
    if cell["initial_marker"]:
        return "初"
    if cell["numeral_value"] is not None:
        return int(cell["numeral_value"])
    attached = cell["marker_reading"]
    if attached["kind"] == "initial":
        return "初"
    if attached["kind"] != "integer":
        raise ValueError("此具名NIJL假设不接收未见附字，不从邻格补数")
    return int(attached["integer_value"])


def _contexts() -> list[dict[str, Any]]:
    grid = load_nijl_grid()
    result = []
    for palace in BRANCHES:
        anchor: dict[str, Any] | None = None
        for column in range(1, 31):
            cell = grid.cell(palace, column)
            if cell["mansion_marker"] is not None:
                anchor = cell
            if anchor is None:
                raise ValueError("区段缺少本行明确宿标，不跨行或取后格补标")
            result.append(
                dict(
                    palace=palace,
                    column=column,
                    literal_label=_label(cell),
                    source_cell=cell,
                    candidate_context=dict(
                        mansion=anchor["mansion_marker"],
                        anchor_column=anchor["column"],
                        anchor_cell=anchor,
                        mansion_printed_at_this_cell=(
                            cell["mansion_marker"] is not None
                        ),
                        policy_id=POLICY,
                        conditional=True,
                        original_usage_adjudicated=False,
                    ),
                )
            )
    return result


def _binding(data: dict[str, Any]) -> dict[str, Any]:
    return dict(
        usage_data_sha256=DATA_SHA256,
        grid_source_id=data["source_grid_id"],
        grid_data_sha256=data["source_grid_data_sha256"],
        grid_image_sha256=data["source_grid_image_sha256"],
        context_policy_id=POLICY,
        original_usage_adjudicated=False,
        ordinary_source_cell_mansion_changed=False,
        initial_converted_to_zero=False,
        continuous_coordinates_accepted=False,
        used_in_native_birth_chart=False,
        real_world_prediction_cases=0,
    )


def conditional_contexts(*, context_policy: str) -> dict[str, Any]:
    """Return every raw cell and its separately marked hypothetical context."""
    _require_policy(context_policy)
    data = _data()
    return dict(**_binding(data), cells=_contexts())


def locate_label(
    *, palace: str, mansion: str, label: int | str, context_policy: str
) -> dict[str, Any]:
    """Keep all matching labels; an empty set never becomes a successful fit."""
    _require_policy(context_policy)
    if not isinstance(palace, str) or palace not in BRANCHES or len(palace) != 1:
        raise ValueError("须明确单个原行宫支，不从现代黄经推定")
    if not isinstance(mansion, str) or mansion not in MANSIONS:
        raise ValueError("须明确原表规范宿名，不由所求目标反推来源宿名")
    if not (
        (type(label) is int and 1 <= label <= 30)
        or (type(label) is str and label == "初")
    ):
        raise ValueError("原字标签须为1至30整数或初；不取整、不将初改为0")
    data = _data()
    row = [r for r in _contexts() if r["palace"] == palace]
    numeral_matches = [r for r in row if r["literal_label"] == label]
    matches = [
        r for r in numeral_matches if r["candidate_context"]["mansion"] == mansion
    ]
    return dict(
        **_binding(data),
        query=dict(palace=palace, mansion=mansion, literal_label=label),
        numeral_only_columns=[r["column"] for r in numeral_matches],
        candidates=matches,
        status="conditional_candidates" if matches else "no_literal_candidate",
        unique_candidate=len(matches) == 1,
        selected_candidate=None,
        target_based_ranking=False,
        column_shift_applied=0,
    )


def audit_intro_usage(*, context_policy: str) -> dict[str, Any]:
    """Locate both source labels before inspecting their same-column targets."""
    _require_policy(context_policy)
    data = _data()
    held = compare_intro_examples()
    contexts = {(r["palace"], r["column"]): r for r in _contexts()}
    cases = []
    note_palaces = set(data["ma591_note_palaces"])
    for old in held["cases"]:
        example = old["example"]
        found = locate_label(
            palace=example["source_branch"],
            mansion=example["source_mansion"],
            label=example["source_degree"],
            context_policy=context_policy,
        )
        targets = []
        for candidate in found["candidates"]:
            target = contexts[(example["target_branch"], candidate["column"])]
            cell = target["source_cell"]
            targets.append(
                dict(
                    source_candidate=candidate,
                    target=target,
                    target_numeric_label_match=(
                        target["literal_label"] == example["target_degree"]
                        if type(target["literal_label"]) is int
                        else None
                    ),
                    target_explicit_mansion_match=(
                        cell["mansion_marker"] == example["target_mansion"]
                        if cell["mansion_marker"] is not None
                        else None
                    ),
                    target_conditional_mansion_context_match=(
                        target["candidate_context"]["mansion"]
                        == example["target_mansion"]
                    ),
                    target_coordinate_semantics_accepted=False,
                )
            )
        columns = [r["column"] for r in found["candidates"]]
        cases.append(
            dict(
                example=example,
                source_lookup=found,
                same_column_targets=targets,
                previously_declared_column=example["declared_column"],
                previous_column_is_the_unique_conditional_candidate=(
                    columns == [example["declared_column"]]
                ),
                all_candidate_targets_are_numeric_counterexamples=(
                    bool(targets)
                    and all(t["target_numeric_label_match"] is False for t in targets)
                ),
                source_or_target_in_ma591_note_palaces=bool(
                    {example["source_branch"], example["target_branch"]} & note_palaces
                ),
            )
        )
    return dict(
        **_binding(data),
        cases=cases,
        case_scope="two_nijl_image8_cases_not_all_cross_book_examples",
        all_original_cases_retained=True,
        existing_literal_comparison=held,
        source_excerpts=data["sources"],
        ma591_note_scope=dict(
            palaces=data["ma591_note_palaces"],
            source_id="ma591_image86",
            note_applied_to_nijl_grid=False,
            only_listed_palace_correction_would_affect_these_cases=any(
                c["source_or_target_in_ma591_note_palaces"] for c in cases
            ),
            conditional_scope_check_only=True,
            angular_or_column_correction_accepted=False,
        ),
        prerequisites_unresolved=data["source_prerequisites_unresolved"],
        circular_chart_three_lines_role_adjudicated=False,
        native_life_degree_accepted=False,
    )
