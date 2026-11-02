"""Attributed volume-five table comparison, separate from governing body/use rules.

The printed vertical columns are transposed into logical state rows in JSON.
Exactly four printed headings are used; no fifth state is reconstructed.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

_PROFILE_SHA256 = "4d22eb831c669bf84db77f0e7a3827cfe6e663f83784b588568c0e72a7103dfa"
_ROLES = ("body", "use", "body_mutual", "use_mutual", "changed_use")
_ROLE_NAMES = ("原体", "初用", "体互", "用互", "变用")
_ELEMENTS = frozenset("木火土金水")
_SEASON_COLUMNS = {
    "春": "春",
    "夏": "夏",
    "秋": "秋",
    "冬": "冬",
    "四季土月": "四季之月",
}


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[1]
        / "data/meihua/volume5-four-state-nlc1925-v1.json"
    )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROFILE_SHA256:
        raise ValueError("Selected volume-five table source bytes changed")
    profile: dict[str, Any] = json.loads(raw)
    if (
        profile["id"] != "meihua_volume5_four_state_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or list(profile["rows"]) != ["旺", "相", "休", "囚"]
        or profile["columns"] != ["春", "夏", "秋", "冬", "四季之月"]
    ):
        raise ValueError("Unknown selected volume-five table layout")
    for i, column in enumerate(profile["columns"]):
        values = [row[i] for row in profile["rows"].values()]
        if len(set(values)) != 4 or not set(values) < _ELEMENTS:
            raise ValueError("Selected volume-five table is not four distinct cells")
        if _ELEMENTS - set(values) != {profile["unlisted_elements_by_column"][column]}:
            raise ValueError("Selected volume-five table absence was rebound")
    return profile


def volume5_strength_ruleset() -> dict[str, Any]:
    """Return a private copy of the visually frozen table and its source scope."""
    return deepcopy(_profile())


def build_volume5_strength_comparison(
    roles: list[dict[str, Any]], seasonal: dict[str, Any] | None
) -> dict[str, Any]:
    """Compare the same declared month without changing primary strength labels."""
    if tuple(row["role"] for row in roles) != _ROLES or any(
        row["element"] not in _ELEMENTS for row in roles
    ):
        raise ValueError("Volume-five comparison requires five actual body/use roles")
    profile = _profile()
    column = None
    month = None
    if seasonal is None:
        if any(
            row["strength"] is not None or row["strength_fact_path"] is not None
            for row in roles
        ):
            raise ValueError("A missing month cannot carry supplied strength labels")
    else:
        month = seasonal["month_branch"]
        if (
            type(month) is not str
            or month not in profile["declared_month_branch_columns"]
        ):
            raise ValueError("Volume-five comparison requires a declared month branch")
        column = profile["declared_month_branch_columns"][month]
        if _SEASON_COLUMNS.get(seasonal["season"]) != column:
            raise ValueError("Month and existing seasonal source context disagree")
        given = seasonal["trigrams"]
        if len(given) != len(roles) or any(
            any(
                row[key] != source[key]
                for key in ["role", "trigram", "element", "strength", "fact_path"]
            )
            for row, source in zip(roles, given, strict=True)
        ):
            raise ValueError(
                "Volume-five comparison and primary labels belong to different casts"
            )
    index = profile["columns"].index(column) if column is not None else None
    compared = []
    for row in roles:
        state = next(
            (
                label
                for label, values in profile["rows"].items()
                if index is not None and values[index] == row["element"]
            ),
            None,
        )
        compared.append(
            {
                "role": row["role"],
                "trigram": row["trigram"],
                "element": row["element"],
                "trigram_fact_path": row["fact_path"],
                "primary_strength": row["strength"],
                "primary_strength_fact_path": row["strength_fact_path"],
                "table_state": state,
                "status": (
                    "month_not_supplied"
                    if index is None
                    else "listed_cell" if state is not None else "element_not_listed"
                ),
                "table_cell_relative_path": (
                    f"ruleset.rows.{state}.{index}" if state is not None else None
                ),
            }
        )
    parts = [
        name
        + row["trigram"]
        + (
            "表列" + row["table_state"]
            if row["table_state"] is not None
            else "本表未列"
        )
        for name, row in zip(_ROLE_NAMES, compared, strict=True)
    ]
    summary = (
        "未提供节月，卷五表只保留原表，当前五个角色不填状态。"
        if index is None
        else f"卷五表同月对照（{column}）：" + "、".join(parts) + "。"
    )
    summary += "原表只有旺、相、休、囚四个状态栏目；既有体用旺衰仍按其所选条款解释，年月日合参未计算。"
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": volume5_strength_ruleset(),
        "source_profile_sha256": _PROFILE_SHA256,
        "source_layout_note": "JSON state rows transpose the printed vertical state columns; no cells are inserted",
        "context_status": (
            "declared_month_comparison" if index is not None else "month_not_supplied"
        ),
        "month_branch": month,
        "table_column": column,
        "primary_month_basis": seasonal["basis"] if seasonal is not None else None,
        "primary_month_mapping_is_software_convention": True,
        "roles": compared,
        "cell_path_basis": "relative_to_this_comparison_object",
        "unlisted_element_in_column": (
            profile["unlisted_elements_by_column"][column]
            if column is not None
            else None
        ),
        "used_to_override_primary_strength": False,
        "governing_body_use_method_adjudicated": False,
        "year_or_day_strength_computed": False,
        "complete_year_month_day_strength_synthesis": None,
        "net_verdict": None,
        "event_time": None,
        "success_probability": None,
        "real_outcome": None,
        "predictive_efficacy_established": False,
        "summary": summary,
    }
