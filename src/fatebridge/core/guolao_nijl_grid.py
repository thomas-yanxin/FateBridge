"""NIJL image77's complete literal grid, kept separate from the MA/591 scan.

This is a source-bound, unblinded collation. Table labels are not accepted
continuous coordinates; 初 is never zero and ordinary cells do not inherit
mansion names. Neither grid is silently selected as a natal calculation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES
from fatebridge.core.guolao_grid import (
    GridCell,
    LifeDegreeGrid,
    MarkerReading,
    load_grid,
)

DATA = Path(__file__).resolve().parents[1] / "data/guolao/nijl-life-grid-v1.json"
DATA_SHA256 = "604685ee3a310ea81539d3a8425cb727be9be6af5bcba7d298e286eaf4830b60"
SOURCE_ID = "nijl_100238879_image77_grid_v1"
SOURCE_SHA256 = "28d84dfea60c2410c4bb40ee596f54311b65aa54b93fdc7b32e07dfe0699d3a0"
EXAMPLES = DATA.with_name("opposite-degree-examples-v1.json")


def _data() -> dict[str, Any]:
    raw = DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATA_SHA256:
        raise ValueError("NIJL源表转写指纹变化，不能静默改字或套用旧校勘")
    result: dict[str, Any] = json.loads(raw)
    if (
        result["source_id"] != SOURCE_ID
        or result["source_image_sha256"] != SOURCE_SHA256
        or "".join(row["palace"] for row in result["rows"]) != BRANCHES
    ):
        raise ValueError("NIJL表须保持具名原图及原行顺序，不能跨扫描拼表")
    return result


def load_nijl_grid() -> LifeDegreeGrid:
    """Read this complete witness without consulting another witness's values."""
    data = _data()
    return LifeDegreeGrid(
        **{
            key: data[key]
            for key in [
                "source_id",
                "source_url",
                "image_url",
                "source_image_sha256",
                "credit",
                "locator",
            ]
        },
        data_sha256=DATA_SHA256,
        rows=tuple(
            tuple(GridCell(**cell) for cell in row["cells"]) for row in data["rows"]
        ),
        marker_readings=tuple(MarkerReading(**item) for item in data["readings"]),
        marker_profile_id=data["profile_id"],
        marker_data_sha256=DATA_SHA256,
    )


def literal_cell(*, palace: str, column: int) -> dict[str, Any]:
    grid = load_nijl_grid()
    return {
        "source_id": grid.source_id,
        "source_image_sha256": grid.source_image_sha256,
        "data_sha256": grid.data_sha256,
        "credit": grid.credit,
        "locator": grid.locator,
        "cell": grid.cell(palace, column),
        "ordinary_mansion_inheritance_applied": False,
        "initial_converted_to_zero": False,
        "used_in_native_birth_chart": False,
    }


def audit_nijl_grid() -> dict[str, Any]:
    result = load_nijl_grid().audit()
    result.update(
        full360_literal_cells_collated=True,
        collation_blind=False,
        independent_second_collator=False,
        full_grid_collation_is_coordinate_acceptance=False,
        comparison_to_other_witnesses_applied=False,
    )
    return result


def _reading(cell: dict[str, Any]) -> dict[str, Any]:
    attached = cell["marker_reading"]
    return dict(
        mansion_marker=cell["mansion_marker"],
        numeral_value=cell["numeral_value"],
        initial_marker=cell["initial_marker"],
        attached_kind=attached["kind"] if attached else None,
        attached_text=attached["text"] if attached else None,
        attached_integer=attached["integer_value"] if attached else None,
    )


def compare_ma591() -> dict[str, Any]:
    """Keep all360 loci, including matching cells and unresolved label meanings."""
    data = _data()
    base, nijl = load_grid(), load_nijl_grid()
    for key, expected in data["comparison_base"].items():
        if getattr(base, key) != expected:
            raise ValueError("MA591比较基准已变化，不能套用NIJL旧校勘绑定")
    cells = []
    for palace in BRANCHES:
        for column in range(1, 31):
            a = _reading(base.cell(palace, column))
            b = _reading(nijl.cell(palace, column))
            cells.append(
                dict(
                    palace=palace,
                    column=column,
                    base=a,
                    nijl=b,
                    same_literal_reading=a == b,
                )
            )
    return dict(
        comparison_id="ma591_nijl_complete360_literal_comparison_v1",
        base_binding=data["comparison_base"],
        nijl_binding=dict(
            source_id=nijl.source_id,
            source_image_sha256=nijl.source_image_sha256,
            data_sha256=nijl.data_sha256,
        ),
        compared_cells=len(cells),
        matching_cells=sum(item["same_literal_reading"] for item in cells),
        different_cells=sum(not item["same_literal_reading"] for item in cells),
        cells=cells,
        differences=[item for item in cells if not item["same_literal_reading"]],
        old_reading_replaced=False,
        column_shift_applied=0,
        independent_second_collator=False,
        textual_genealogy_established=False,
        life_degree_accepted=False,
    )


def _literal_integer(cell: dict[str, Any]) -> int | None:
    value = cell["numeral_value"]
    if value is None:
        attached = cell["marker_reading"]
        value = attached["integer_value"] if attached else None
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("原格数值须为明确整数标签，不隐式换算浮点或真假值")
    return value


def compare_intro_examples() -> dict[str, Any]:
    """The two NIJL image8 clauses versus the explicitly selected table columns.

    A printed integer label is compared as text/number, not as an exact source
    coordinate. Column15/29 and the target branch remain explicit research
    choices, not inferred birth positions or an adjudicated use of the table.
    """
    data = _data()
    raw = EXAMPLES.read_bytes()
    if hashlib.sha256(raw).hexdigest() != data["intro_example_data_sha256"]:
        raise ValueError("原例资料指纹变化，不能删例或套用旧表位置")
    reference = json.loads(raw)
    examples = [
        item for item in reference["cases"] if item["id"] in data["intro_example_ids"]
    ]
    if [item["id"] for item in examples] != data["intro_example_ids"]:
        raise ValueError("须齐全保留本见证的两条入门原例")
    source = next(
        item
        for item in reference["sources"]
        if item["id"] == "luwei_nijl100238879_image8"
    )
    grid = load_nijl_grid()
    cases = []
    for example in examples:
        a = grid.cell(example["source_branch"], example["declared_column"])
        b = grid.cell(example["target_branch"], example["declared_column"])
        source_number = _literal_integer(a)
        number = _literal_integer(b)
        cases.append(
            dict(
                example=example,
                source_cell=a,
                target_cell=b,
                target_literal_integer=number,
                target_numeric_label_match=(
                    number == example["target_degree"] if number is not None else None
                ),
                target_explicit_mansion_match=(
                    b["mansion_marker"] == example["target_mansion"]
                    if b["mansion_marker"] is not None
                    else None
                ),
                source_numeric_label_match=(
                    source_number == example["source_degree"]
                    if source_number is not None
                    else None
                ),
                source_coordinate_semantics_accepted=False,
                column_shift_applied=0,
            )
        )
    return dict(
        comparison_id="nijl_image8_image77_two_explicit_column_examples_v1",
        table_source_id=grid.source_id,
        table_data_sha256=grid.data_sha256,
        example_source=source,
        example_data_sha256=hashlib.sha256(raw).hexdigest(),
        cases=cases,
        all_same_column_numeric_examples_agree=all(
            item["target_numeric_label_match"] is True for item in cases
        ),
        exact_coordinate_or_quantization_policy_accepted=False,
        selected_table_usage_adjudicated=False,
        life_degree_accepted=False,
        used_in_native_birth_chart=False,
        real_world_prediction_cases=0,
    )
