"""Printed-table diagnostics independent of the Qimen calculation engine.

This tests a declared numeric walk against the retained raw transcription.
It cannot establish a correct emendation, authenticate a scan's lineage or
turn agreement with that walk into whole-book conformance.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HEADS = ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")


def audit_table_source_context(directory: Path) -> dict[str, Any]:
    """Retain manually observed bibliography without laundering it into a scan."""
    path = directory / "source-diagnostics.json"
    context = json.loads(path.read_text())
    excerpt = (directory / context["excerpt_file"]).resolve()
    if not excerpt.is_relative_to(directory.resolve()):
        raise ValueError("数表语境影印路径越出参考目录")
    if hashlib.sha256(excerpt.read_bytes()).hexdigest() != context["excerpt_sha256"]:
        raise ValueError("数表语境影印指纹不一致")
    records = context["catalogue_observations"]
    required = {"故庫018065-018066", "NTUT-9910018322", "NTUT-9910018324"}
    if len(records) != 3 or {r["identifier"] for r in records} != required:
        raise ValueError("须保留三条书目观察，不能删除未数字化或未读到的记录")
    for record in records:
        if (
            record.get("readable_rule_images_verified") is not False
            or record.get("selected_third_party_pdf_lineage_authenticated") is not False
        ):
            raise ValueError("本组仅有书目观察，不能升级为规则书页或所选PDF来源认证")
    npm = next(r for r in records if r["identifier"] == "故庫018065-018066")
    binding_conflict = npm["main_binding"] != npm["extended_binding"]
    return {
        "method_id": "qimen_manually_observed_catalogue_scope_v1",
        "context_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "context_excerpt_sha256": context["excerpt_sha256"],
        "context_section": context["context_section"],
        "context_scope": context["context_scope"],
        "observation_date": context["catalogue_observations_at"],
        "catalogue_observations": records,
        "catalogue_observations_live_rechecked_by_this_function": False,
        "bibliographic_binding_fields_conflict": binding_conflict,
        "binding_priority_resolved": not binding_conflict,
        "institutional_rule_pages_read": sum(
            r["readable_rule_images_verified"] for r in records
        ),
        "selected_scan_lineage_authenticated": False,
        "scope": "Checks retained local observations and excerpt hashes, not live web truth, institutional endorsements or a link between a matching title and the selected third-party PDF.",
    }


def _hour(column: int, row: int) -> str:
    index = 10 * column + row
    return "甲乙丙丁戊己庚辛壬癸"[row] + "子丑寅卯辰巳午未申酉戌亥"[index % 12]


def unrepresented_walk_anomalies(
    integrity: dict[str, Any], engine_disagreements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    fields = ("dun", "ju", "hour", "field")
    represented = {tuple(d[k] for k in fields) for d in engine_disagreements}
    return [
        d
        for d in integrity["anomalous_cells"]
        if tuple(d[k] for k in fields) not in represented
    ]


def audit_printed_table_integrity(directory: Path) -> dict[str, Any]:
    manifest_path = directory / "sources-and-tables.json"
    manifest = json.loads(manifest_path.read_text())
    excerpt = (directory / manifest["excerpt_file"]).resolve()
    if not excerpt.is_relative_to(directory.resolve()):
        raise ValueError("数表诊断影印路径越出参考目录")
    if hashlib.sha256(excerpt.read_bytes()).hexdigest() != manifest["excerpt_sha256"]:
        raise ValueError("数表诊断影印参考文件指纹不一致")
    tables = manifest["tables"]
    required = {(d, j) for d in ("阳遁", "阴遁") for j in range(1, 10)}
    if len(tables) != 18 or {(t["dun"], t["ju"]) for t in tables} != required:
        raise ValueError("数表诊断必须保留完整十八局，不得删局或重复")
    anomalous_cells: list[dict[str, Any]] = []
    edge_defects: list[dict[str, Any]] = []
    closure_defects: list[dict[str, Any]] = []
    columns = 0
    for table in tables:
        if tuple(table["column_order"]) != HEADS or len(table["palace_pairs"]) != 6:
            raise ValueError("数表诊断须保留每局六旬及原列序")
        step = 1 if table["dun"] == "阳遁" else -1
        for column, text in enumerate(table["palace_pairs"]):
            tokens = text.split()
            if len(tokens) != 10 or any(
                len(t) != 2 or any(c not in "123456789" for c in t) for t in tokens
            ):
                raise ValueError("数表诊断须保留每旬十时及两位原始宫数")
            columns += 1
            doors = [int(t[1]) for t in tokens]
            context = {
                "dun": table["dun"],
                "ju": table["ju"],
                "column_xun": HEADS[column],
                "table_scan_page": table["table_scan_page"],
                "table_half": table["table_half"],
                "raw_door_sequence": doors,
            }
            # Anchor in the first PRINTED number, not an engine-derived earth
            # plate. Raw centre 5 remains 5; no Kun hosting enters this test.
            for row, printed in enumerate(doors):
                implied = (doors[0] - 1 + step * row) % 9 + 1
                if printed != implied:
                    anomalous_cells.append(
                        {
                            **context,
                            "hour": _hour(column, row),
                            "field": "raw_door_gong",
                            "raw_pair": tokens[row],
                            "printed_number": printed,
                            "walk_implied_number": implied,
                            "row_offset_from_printed_head": row,
                            "status": "inconsistent_with_declared_walk_not_an_accepted_emendation",
                        }
                    )
                if row and printed != (doors[row - 1] - 1 + step) % 9 + 1:
                    edge_defects.append(
                        {
                            **context,
                            "from_hour": _hour(column, row - 1),
                            "to_hour": _hour(column, row),
                            "printed_from": doors[row - 1],
                            "printed_to": printed,
                        }
                    )
            if doors[-1] != doors[0]:
                closure_defects.append(
                    {
                        **context,
                        "first_hour": _hour(column, 0),
                        "last_hour": _hour(column, 9),
                        "printed_first": doors[0],
                        "printed_last": doors[-1],
                    }
                )
    return {
        "method_id": "qimen_printed_numeric_walk_integrity_v1",
        "source": manifest["source_url"],
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "excerpt_sha256": manifest["excerpt_sha256"],
        "hypothesis": "Raw nine-palace numeric walk, +1 per elapsed hour in yang dun and -1 in yin dun, anchored separately in each printed head row; raw 5 is not hosted to 2.",
        "hypothesis_status": "Declared diagnostic consistent with the selected algorithm; not a new independently authenticated full classical rule.",
        "production_engine_used": False,
        "absolute_head_placement_validated": False,
        "star_numbers_validated": False,
        "printed_column_count": columns,
        "printed_hour_rows": columns * 10,
        "adjacent_transition_checks": columns * 9,
        "nine_step_closure_checks": columns,
        "anomalous_cells": anomalous_cells,
        "adjacent_transition_defects": edge_defects,
        "nine_step_closure_defects": closure_defects,
        "status": (
            "printed_walk_inconsistencies_retained"
            if anomalous_cells
            else "consistent_with_declared_walk"
        ),
        "source_numbers_rewritten": False,
        "printing_error_established": False,
        "emendation_adopted": False,
        "independent_new_reference_cases": 0,
        "whole_book_conformance_established": False,
        "real_world_efficacy_validated": False,
    }
