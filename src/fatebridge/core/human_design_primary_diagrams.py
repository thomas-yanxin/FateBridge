"""Narrow, attributed diagram observations, retaining unresolved source faults."""

import hashlib
from copy import deepcopy
from typing import Any

from fatebridge.core.human_design_references import reference_bytes, reference_data

METHOD = "human_design_primary_transcript_diagrams_v1"
SCOPE = "只匹配已核看的两幅公开转录图之有序四门与左角度；不由单门、相似名字或角色推断匹配。原页5/1段落不充当其他角色线义；未经校对的公开副本不认证出版方母本，也不是16/6课程列项的勘误。不改写2001版名称、门线、固定极性或原有失败。"


def diagram_reference() -> dict[str, Any]:
    return reference_data("primary-diagrams-2008-reference.json")


def _raw() -> bytes:
    return reference_bytes("primary-diagrams-2008-reference.json")


def primary_diagram_evidence(chart: dict[str, Any]) -> dict[str, Any]:
    cross = chart["incarnation_cross"]
    reference = diagram_reference()
    matching = [
        row
        for row in reference["observations"]
        if row["gates"] == cross["gates"] and row["angle"] == cross["angle"]
    ]
    result = {
        "method_id": METHOD,
        "status": (
            "observed_same_ordered_quartet_and_angle"
            if matching
            else "not_observed_in_two_diagrams"
        ),
        "primary_2001_name": cross["name"],
        "primary_2001_name_retained": True,
        "observations": deepcopy(matching),
        "catalog_sha256": hashlib.sha256(_raw()).hexdigest(),
        "attributed_author": reference["attributed_author"],
        "attributed_publisher": reference["attributed_publisher"],
        "title": reference["title"],
        "copyright_year": reference["copyright_year"],
        "proof_notice": reference["proof_notice"],
        "transcription_proofed": False,
        "publisher_master_authenticated": False,
        "publisher_erratum_obtained": False,
        "all_source_disagreements_resolved": False,
        "full_source_acceptance_passed": False,
        "scope": SCOPE,
    }
    result["reading"] = primary_diagram_reading(result) if matching else None
    return result


def primary_diagram_reading(record: dict[str, Any]) -> str:
    if not record["observations"]:
        raise ValueError("No inspected source diagram matches this quartet and angle")
    parts = []
    for row in record["observations"]:
        a, b, c, d = row["gates"]
        parts.append(
            f"公开2008转录本卷{row['quarter']}的PDF第{row['pdf_page_one_based']}页（印刷第{row['printed_page']}页）"
            f"图示{a}/{b}｜{c}/{d}，编号为{row['display_identifier']}，与本盘有序四门及左角度相同。"
        )
    return "".join(parts) + (
        f"本盘仍保留2001版名称{record['primary_2001_name']}，不把不同编号归为字面一致。"
        "转录本明确未经校对，公开副本未认证为出版方母本；这不是16/6课程列项的勘误。"
        "该图所在段落为5/1，只核对图示四门及角度，不扩成其他角色或完整线义，也不改写激活或关闭既有原典失败。"
    )
