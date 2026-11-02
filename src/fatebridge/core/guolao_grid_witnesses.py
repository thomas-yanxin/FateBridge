"""Four collated locations in three named scans, without merging their grids.

This is a partial textual comparison. Agreement of witnesses neither repairs
the base scan nor establishes the meaning of the table as a life degree.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES
from fatebridge.core.guolao_grid import (
    GridCell,
    LifeDegreeGrid,
    MarkerReading,
    load_grid,
)

DATA = Path(__file__).resolve().parents[1] / "data/guolao/grid-witnesses-v1.json"


@dataclass(frozen=True)
class WitnessCell:
    witness_id: str
    palace: str
    column: int
    cell: GridCell
    attached: MarkerReading

    def __post_init__(self) -> None:
        if not self.witness_id:
            raise ValueError("须明确具名扫描，不接受无来源的校正值")
        if (
            self.attached.palace != self.palace
            or self.attached.column != self.column
            or self.attached.mansion != self.cell.mansion_marker
        ):
            raise ValueError("附字须与同一扫描、宫支、列号和宿标对应")

    def reading(self) -> dict[str, Any]:
        return {
            "mansion_marker": self.cell.mansion_marker,
            "numeral_value": self.cell.numeral_value,
            "initial_marker": self.cell.initial_marker,
            "attached_text": self.attached.text,
            "attached_kind": self.attached.kind,
            "attached_integer": self.attached.integer_value,
        }


def _base_reading(grid: LifeDegreeGrid, palace: str, column: int) -> dict[str, Any]:
    cell = grid.cell(palace, column)
    attached = cell["marker_reading"]
    return {
        "mansion_marker": cell["mansion_marker"],
        "numeral_value": cell["numeral_value"],
        "initial_marker": cell["initial_marker"],
        "attached_text": attached["text"] if attached else None,
        "attached_kind": attached["kind"] if attached else None,
        "attached_integer": attached["integer_value"] if attached else None,
    }


def compare_witnesses(*, palace: str, column: int) -> dict[str, Any]:
    """Read only a collated locus; unknown positions are never filled by a peer."""
    if palace not in BRANCHES or len(palace) != 1:
        raise ValueError("须明确单个宫支")
    if isinstance(column, bool) or not isinstance(column, int):
        raise TypeError("列号须为明确整数")
    if not 1 <= column <= 30:
        raise ValueError("列号须在1至30，不移列或取模")
    raw = DATA.read_bytes()
    data = json.loads(raw)
    grid = load_grid()
    binding = data["base_binding"]
    if any(
        binding[key] != getattr(grid, key)
        for key in [
            "source_id",
            "source_image_sha256",
            "data_sha256",
            "marker_data_sha256",
        ]
    ):
        raise ValueError("基准扫描或转录已变化，须重新校勘，不能跨版本套用")
    sources = data["witnesses"]
    if not sources:
        raise ValueError("须有明确的对校扫描")
    if len({s["id"] for s in sources}) != len(sources):
        raise ValueError("具名扫描重复")
    expected_ids = {s["id"] for s in sources}
    loci = data["loci"]
    positions = [(locus["palace"], locus["column"]) for locus in loci]
    if len(set(positions)) != len(positions):
        raise ValueError("已校位置重复")
    matches = [
        locus
        for locus in loci
        if (palace, column) == (locus["palace"], locus["column"])
    ]
    if not matches:
        raise ValueError("此位置未校勘，不能由其他列、底本或邻格补齐")
    locus = matches[0]
    readings = tuple(
        WitnessCell(
            witness_id=r["witness_id"],
            palace=palace,
            column=column,
            cell=GridCell(**r["cell"]),
            attached=MarkerReading(palace=palace, column=column, **r["attached"]),
        )
        for r in locus["readings"]
    )
    if (
        len(readings) != len(expected_ids)
        or {r.witness_id for r in readings} != expected_ids
    ):
        raise ValueError("每个位置须分别记录全部具名扫描，不能借另一底本补字")
    base = _base_reading(grid, palace, column)
    return {
        "collation_id": data["id"],
        "collation_data_sha256": hashlib.sha256(raw).hexdigest(),
        "status": "partial_literal_witness_comparison",
        "palace": palace,
        "column": column,
        "base": {
            "binding": binding,
            "reading": base,
            "credit": grid.credit,
            "source_url": grid.source_url,
        },
        "witnesses": [
            {
                "source": next(s for s in sources if s["id"] == reading.witness_id),
                "reading": reading.reading(),
                "differs_from_base": reading.reading() != base,
            }
            for reading in readings
        ],
        "witness_readings_agree": all(
            r.reading() == readings[0].reading() for r in readings
        ),
        "full_grid_collated": False,
        "second_independent_collator": False,
        "textual_genealogy_established": False,
        "base_reading_replaced": False,
        "column_shift_applied": 0,
        "life_degree_accepted": False,
        "used_in_native_birth_chart": False,
    }
