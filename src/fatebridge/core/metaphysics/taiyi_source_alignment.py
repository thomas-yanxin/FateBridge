"""Separate returned positions/counts from literal table and source recounts."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_SHA256 = "e3da8f35487b57146dcec7e2ef5e599d6254d808841dbfed87599d483e27868a"
FIELDS = ("taiyi_number", "wenchang_palace", "shiji", "jishen")
LITERAL_FIELDS = {
    "wenchang_palace": "wenchang_literal",
    "shiji": "shiji_literal",
    "jishen": "jishen_literal",
}


@lru_cache(maxsize=1)
def source_catalog() -> tuple[dict[str, Any], dict[tuple[bool, int], Any]]:
    path = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-jinjing-source-alignment-v1.json"
    )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("太乙原表位置资料指纹不符")
    data = json.loads(raw)
    rows = {(r["yin"], r["ju"]): r for r in data["rows"]}
    if len(rows) != 144:
        raise ValueError("太乙原表须保留完整阴阳144局")
    return data, rows


def count_source_assessment(core: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.metaphysics.taiyi_edition_witness import (
        edition_comparisons,
    )
    from fatebridge.core.metaphysics.taiyi_geometry import (
        BRANCHES,
        PALACES,
        RING,
        count_to_taiyi,
    )

    data, rows = source_catalog()
    ruleset = {
        k: data[k]
        for k in (
            "id",
            "version",
            "author",
            "classical_author",
            "source_title",
            "facsimile_source",
            "source",
            "count_rule_source",
            "source_manifest_sha256",
            "transcription_collation_manifest_sha256",
            "facsimile_collation_manifest_sha256",
            "facsimile_correction_manifest_sha256",
        )
    }
    ruleset["catalog_sha256"] = CATALOG_SHA256
    required = (*FIELDS, "main_count", "guest_count")
    valid = (
        type(core.get("yin_dun")) is bool
        and type(core.get("kook_number")) is int
        and type(core.get("accumulation")) is int
        and core["accumulation"] > 0
        and core["kook_number"] == (core["accumulation"] - 1) % 72 + 1
        and all(k in core for k in required)
        and type(core["taiyi_number"]) is int
        and core["taiyi_number"] in PALACES
        and core["taiyi_number"] != 5
        and core.get("taiyi_palace") == PALACES[core["taiyi_number"]]
        and all(type(core[k]) is str for k in ("wenchang_palace", "shiji", "jishen"))
        and core["wenchang_palace"] in set(RING)
        and core["shiji"] in set(RING)
        and core["jishen"] in set(BRANCHES)
        and all(
            type(core[k]) is int and 1 <= core[k] <= 40
            for k in ("main_count", "guest_count")
        )
    )
    if not valid:
        return {
            "ruleset": ruleset,
            "status": "not_assessed",
            "reason": "同次阴阳/局序/核心缺失或不一致，不默认按阳局或猜源行。",
            "positions": [],
            "counts": [],
            "facsimile_readings": [],
            "edition_comparisons": [],
            "scope": data["scope"],
        }
    row = rows[(core["yin_dun"], core["kook_number"])]
    positions = []
    for field in FIELDS:
        literal_field = LITERAL_FIELDS.get(field)
        checks = [c for c in row["facsimile_checks"] if c["field"] == literal_field]
        layer = (
            "selected_facsimile"
            if any(c["selected_reading"] == "facsimile" for c in checks)
            else (
                "primary_facsimile_semantic_collation"
                if field in row["facsimile_semantic_collation"]["fields"]
                else "primary_transcription_not_individually_facsimile_checked"
            )
        )
        positions.append(
            {
                "field": field,
                "actual_path": (
                    field if field == "wenchang_palace" else "core_board." + field
                ),
                "actual_value": core[field],
                "source_value": row["positions"][field],
                "source_literal": (
                    row["selected_literals"][literal_field]
                    if literal_field
                    else str(row["positions"][field])
                ),
                "transcription_literal": (
                    row["transcription_literals"][literal_field]
                    if literal_field
                    else str(row["positions"][field])
                ),
                "initial_manual_literal": (
                    row["initial_manual_literals"][literal_field]
                    if literal_field
                    else str(row["positions"][field])
                ),
                "source_layer": layer,
                "matches": core[field] == row["positions"][field],
            }
        )
    counts = []
    for camp, marker_field in (("main", "wenchang_palace"), ("guest", "shiji")):
        field = camp + "_count"
        table = row["table_counts"][field]
        source_marker = row["positions"][marker_field]
        recount = count_to_taiyi(source_marker, row["positions"]["taiyi_number"])
        matches = core[field] == table
        same_inputs = (
            core[marker_field] == source_marker
            and core["taiyi_number"] == row["positions"]["taiyi_number"]
        )
        rec_matches = recount["count"] == table
        if matches:
            diagnosis = (
                "agrees_with_selected_source_inputs_and_count"
                if same_inputs
                else "count_agrees_despite_source_input_difference"
            )
        elif same_inputs:
            diagnosis = "same_position_rule_table_disagreement"
        elif rec_matches:
            diagnosis = "source_inputs_explain_count_difference"
        else:
            diagnosis = "source_input_and_count_disagreements"
        counts.append(
            {
                "camp": camp,
                "field": field,
                "marker_field": marker_field,
                "actual_count_path": "core_board." + field,
                "actual_marker_path": (
                    marker_field
                    if marker_field == "wenchang_palace"
                    else "core_board." + marker_field
                ),
                "actual_marker": core[marker_field],
                "source_marker": source_marker,
                "actual_count": core[field],
                "source_table_count": table,
                "source_layer": "primary_facsimile_semantic_collation",
                "count_matches": matches,
                "same_inputs": same_inputs,
                "source_recount_matches_table": rec_matches,
                "source_position_recount": recount,
                "diagnosis": diagnosis,
            }
        )
    position_diffs = [p["field"] for p in positions if not p["matches"]]
    count_diffs = [c["field"] for c in counts if not c["count_matches"]]
    internal_diffs = [
        c["field"] for c in counts if not c["source_recount_matches_table"]
    ]
    return {
        "ruleset": ruleset,
        "status": "assessed_selected_table_columns",
        "case_id": row["id"],
        "yin_dun": row["yin"],
        "ju": row["ju"],
        "facsimile_page": row["facsimile_semantic_collation"]["page"],
        "facsimile_columns_from_right": list(
            row["facsimile_semantic_collation"]["columns_from_right"]
        ),
        "positions": positions,
        "counts": counts,
        "facsimile_readings": [dict(check) for check in row["facsimile_checks"]],
        "edition_comparisons": edition_comparisons(
            core["yin_dun"],
            core["kook_number"],
            {fact["field"]: fact["actual_value"] for fact in positions}
            | {fact["field"]: fact["actual_count"] for fact in counts},
            {fact["field"]: fact["source_value"] for fact in positions}
            | {fact["field"]: fact["source_table_count"] for fact in counts},
            {fact["field"]: fact["source_literal"] for fact in positions}
            | {fact["field"]: str(fact["source_table_count"]) for fact in counts},
        ),
        "summary": {
            "status": (
                "differences_unadjudicated"
                if position_diffs or count_diffs or internal_diffs
                else "selected_columns_agree"
            ),
            "position_disagreements": position_diffs,
            "count_disagreements": count_diffs,
            "source_internal_count_disagreements": internal_diffs,
            "scope": "仅本局所选四位置/两算；相符不等于全盘、古历或全书符合。",
        },
        "scope": data["scope"]
        + "源位置重算只核原表内部关系，不替换本次盘，不自动裁定原书或通则何者有误。",
    }


def source_alignment_text(assessment: dict[str, Any]) -> str:
    if assessment["status"] == "not_assessed":
        return str(assessment["reason"])
    labels = {"main": "主算", "guest": "客算"}
    lines = [
        f"卷三源表位置/两算校读：{'阴' if assessment['yin_dun'] else '阳'}遁{assessment['ju']}局。"
    ]
    names = {
        "taiyi_number": "太乙宫数",
        "wenchang_palace": "文昌",
        "shiji": "始击",
        "jishen": "计神",
        "main_count": "主算",
        "guest_count": "客算",
    }
    for fact in assessment["positions"]:
        if not fact["matches"]:
            lines.append(
                f"{names[fact['field']]}：本盘{fact['actual_value']}，所读原表{fact['source_literal']}→{fact['source_value']}，位置不合未裁定。"
            )
    for fact in assessment["counts"]:
        if (
            not fact["count_matches"]
            or not fact["same_inputs"]
            or not fact["source_recount_matches_table"]
        ):
            rec = fact["source_position_recount"]
            lines.append(
                f"{labels[fact['camp']]}：本盘目{fact['actual_marker']}、算{fact['actual_count']}；原表目{fact['source_marker']}、算{fact['source_table_count']}；把原表位置按所选卷二通则重算为{rec['count']}，加数{' + '.join(str(p['value']) for p in rec['path'])}。重算不是本盘替代值，差异保留。"
            )
    for check in assessment["facsimile_readings"]:
        if check["status"] == "transcription_differs_from_facsimile":
            lines.append(
                f"图{check['page']}校读：转录{check['text_reading']}，书影{check['facsimile_reading']}；保留原字并明示所选层。"
            )
        elif (
            check["status"] == "initial_manual_entry_differs_from_source_and_facsimile"
        ):
            lines.append(
                f"初录整理误写{check['initial_manual_reading']}；旧转录与图{check['page']}书影均为{check['facsimile_reading']}。此为本次录入错误，不是旧转录错误；初录保留。"
            )
    for witness in assessment["edition_comparisons"]:
        facts = "、".join(
            f"{names[f['field']]}：{f['edition_literal']}→{f['edition_value']}"
            for f in witness["observations"]
        )
        polarity = "阴" if witness["yin_dun"] else "阳"
        lines.append(
            f"具名版本旁证：{witness['provider']}藏{witness['source_title']}，{witness['edition']}，"
            f"{polarity}{witness['ju']}局{facts}；"
            f"本盘与该版所选{witness['required_observations']}项相合{witness['matching_current_observations']}项。"
            + witness["scope"]
        )
    lines.append(assessment["summary"]["scope"])
    return "\n".join(lines)
