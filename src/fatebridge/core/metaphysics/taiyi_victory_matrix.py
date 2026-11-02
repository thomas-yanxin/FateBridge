"""Same-board classical column references and qualified geometric comparisons."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_geometry import PALACES, RING

CATALOG_SHA256 = "a7ed6774b748742e4fc44649ad171057d8f61d8c4fd3a577189784f46940e41d"
GEOMETRY_CLAUSE = re.compile(r"^(天目|大將|參將|小將|大小將)(內迫|外迫|迫|囚|格)$")
OUTCOME_CLAUSE = re.compile(
    r"^(?:(?:主人?|客)(?:大|小)?[勝敗])+$|^(?:不利|利)?先起(?:敗)?$|^(?:先勝後[敗負]|客先起|後敗)$"
)
SUBJECTS = [
    ("wenchang_palace", "文昌", "wenchang_palace"),
    ("main_general", "主大将", "core_board.main_general"),
    ("main_vice_general", "主参将", "core_board.main_vice_general"),
    ("guest_general", "客大将", "core_board.guest_general"),
    ("guest_vice_general", "客参将", "core_board.guest_vice_general"),
]


@lru_cache(maxsize=1)
def source_catalog() -> dict[str, Any]:
    p = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-victory-matrix-v1.json"
    )
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("胜败钤资料指纹不符")
    data: dict[str, Any] = json.loads(raw)
    if len(data["cells"]) != 128:
        raise ValueError("胜败钤须保留全部128格")
    return data


def _geometry(core: dict[str, Any], taiyi: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field, label, path in SUBJECTS:
        value = core.get(field)
        position = (
            value
            if field == "wenchang_palace" and type(value) is str
            else PALACES.get(value) if type(value) is int else None
        )
        valid = type(position) is str and position in RING
        distance = (
            (RING.index(position) - RING.index(taiyi)) % 16
            if isinstance(position, str) and valid
            else None
        )
        rows.append(
            {
                "field": field,
                "label": label,
                "actual_path": path,
                "position": position,
                "distance": distance,
                "status": "computed_ring_geometry" if valid else "not_assessed",
                "same_palace": distance == 0 if valid else None,
                "opposite": distance == 8 if valid else None,
                "inner_adjacent": distance in (14, 15) if valid else None,
                "outer_adjacent": distance in (1, 2) if valid else None,
                "adjacent": distance in (1, 2, 14, 15) if valid else None,
            }
        )
    return rows


def _clauses(
    cell: dict[str, Any], geometry: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    facts = {r["field"]: r for r in geometry}
    rows: list[dict[str, Any]] = []
    for column in ["condition_column", "result_column"]:
        raw = cell[column]["text"]
        if raw is None:
            rows.append(
                {
                    "column": column,
                    "text": None,
                    "kind": "blank_retained",
                    "candidates": [],
                }
            )
            continue
        for text in re.split("[／；]", raw):
            row: dict[str, Any] = {"column": column, "text": text, "candidates": []}
            match = GEOMETRY_CLAUSE.fullmatch(text)
            if match:
                actor, relation = match.groups()
                predicate = {
                    "內迫": "inner_adjacent",
                    "外迫": "outer_adjacent",
                    "迫": "adjacent",
                    "囚": "same_palace",
                    "格": "opposite",
                }[relation]
                fields = (
                    ["wenchang_palace"]
                    if actor == "天目"
                    else (
                        ["main_general", "guest_general"]
                        if actor == "大將"
                        else (
                            [
                                "main_general",
                                "main_vice_general",
                                "guest_general",
                                "guest_vice_general",
                            ]
                            if actor == "大小將"
                            else ["main_vice_general", "guest_vice_general"]
                        )
                    )
                )
                row.update(
                    kind="geometric_claim",
                    actor=actor,
                    predicate=predicate,
                    role_resolution=(
                        "table_eye_wenchang"
                        if actor == "天目"
                        else "camp_unadjudicated"
                    ),
                    source_name_scope="只比较同宫、对宫或环位邻接；格/对、迫的异称和完整适用另待裁定。",
                    candidates=[
                        {
                            "field": field,
                            "actual_path": facts[field]["actual_path"],
                            "position": facts[field]["position"],
                            "matches_geometry": facts[field][predicate],
                        }
                        for field in fields
                    ],
                )
            else:
                row["kind"] = (
                    "literal_outcome_only"
                    if OUTCOME_CLAUSE.fullmatch(text)
                    else "unadjudicated_clause"
                )
            rows.append(row)
    return rows


def victory_matrix_assessment(
    core: dict[str, Any], *, calculation_mode: str | None = None
) -> dict[str, Any]:
    if calculation_mode not in {None, "year", "month", "day", "hour"}:
        raise ValueError("胜败钤时间层须为明确计法或未知")
    data = source_catalog()
    result: dict[str, Any] = {
        "ruleset": {
            **{
                k: data[k]
                for k in [
                    "id",
                    "version",
                    "author",
                    "classical_author",
                    "source_title",
                    "source_manifest_sha256",
                    "source_urls",
                ]
            },
            "catalog_sha256": CATALOG_SHA256,
        },
        "calculation_mode": calculation_mode,
        "role_scope": data["role_scope"],
        "method_scope": data["method_scope"],
        "scope": data["scope"],
        "table_applicability_verified": False,
        "source_outcome_applied": False,
        "classical_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }
    n, eye, taiyi = (
        core.get("taiyi_number"),
        core.get("wenchang_palace"),
        core.get("taiyi_palace"),
    )
    if (
        type(n) is not int
        or n not in (1, 2, 3, 4, 6, 7, 8, 9)
        or type(eye) is not str
        or eye not in set(RING)
        or taiyi != PALACES[n]
    ):
        result.update(
            status="not_assessed",
            reason="太乙数、实际宫位或本表文昌位置缺失、无效或互不相符；不猜查表键。",
        )
        result["ruleset"] = copy.deepcopy(result["ruleset"])
        return result
    cell = next(
        c
        for c in data["cells"]
        if c["wenchang_position"] == eye and c["taiyi_number"] == n
    )
    geometry = _geometry(core, taiyi)
    clauses = _clauses(cell, geometry)
    eye_claims = [
        c["candidates"][0]["matches_geometry"]
        for c in clauses
        if c.get("role_resolution") == "table_eye_wenchang"
    ]
    result.update(
        status="source_cell_retrieved_geometry_compared",
        source_cell=copy.deepcopy(cell),
        actual_geometry=geometry,
        clauses=clauses,
        comparison_summary={
            "resolved_eye_claims": len(eye_claims),
            "matching_eye_geometry": sum(x is True for x in eye_claims),
            "different_eye_geometry": sum(x is False for x in eye_claims),
            "unknown_eye_geometry": sum(x is None for x in eye_claims),
            "unqualified_general_claims": sum(
                c.get("role_resolution") == "camp_unadjudicated" for c in clauses
            ),
            "unadjudicated_clauses": sum(
                c["kind"] == "unadjudicated_clause" for c in clauses
            ),
            "blank_columns": sum(c["kind"] == "blank_retained" for c in clauses),
            "source_lacuna": cell["reading_status"] == "lacuna_retained",
            "whole_cell_conformance_assessed": False,
        },
    )
    result["ruleset"] = copy.deepcopy(result["ruleset"])
    return result


def victory_matrix_text(a: dict[str, Any]) -> str:
    if a["status"] == "not_assessed":
        return str(a["reason"])
    cell = a["source_cell"]
    conditions = cell["condition_column"]["text"]
    reading = cell["result_column"]["text"]
    text = f"胜败钤原栏参照：本盘文昌{cell['wenchang_position']}（{cell['source_spirit']}）、太乙{cell['taiyi_number']}宫；条件栏「{conditions if conditions is not None else '空栏'}」，结果栏「{reading if reading is not None else '空栏'}」。"
    diffs = a["comparison_summary"]["different_eye_geometry"]
    if diffs:
        text += f"其中{diffs}条天目几何文字与本盘所用十六神环位不符，差异保留，未改盘迎合原栏。"
    return text + str(a["role_scope"]) + str(a["method_scope"]) + str(a["scope"])
