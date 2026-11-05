"""Disclose fixed-edition source differences without rewriting a computed chart."""

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, cast

DATA = Path(__file__).parents[2] / "data/fengshui/shen-natal-source-comparison-v2.json"
DATA_SHA256 = "2ccb614c5fbfca1533633a975cda520d1dbbdee6db3a9b3ac3715b02ff5cdd7e"
MOUNTAINS = "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬"
DIRECTIONS = ("C", "NW", "W", "NE", "S", "N", "SW", "E", "SE")
ROLES = ("period", "mountain", "facing")


@lru_cache(maxsize=1)
def _bundle() -> Dict[str, Any]:
    raw = DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATA_SHA256:
        raise RuntimeError("Packaged Shen source facts differ from their fixed edition")
    data = cast(Dict[str, Any], json.loads(raw))
    for field in ("rows", "replacement_rows"):
        keys = {(r["period"], r["facing_mountain"]) for r in data[field]}
        if len(data[field]) != 216 or keys != {
            (period, mountain) for period in range(1, 10) for mountain in MOUNTAINS
        }:
            raise RuntimeError(
                "All 216 distinct source associations per mode are required"
            )
    return data


def comparison_provenance() -> Dict[str, Any]:
    data = _bundle()
    return {
        **deepcopy(data["ruleset"]),
        "sources": [deepcopy(data["source"]), deepcopy(data["replacement_source"])],
        "source_freezes": deepcopy(data["source_freezes"]),
        "packaged_source_sha256": DATA_SHA256,
        "corpus": deepcopy(data["corpus"]),
    }


def _integrity(chart: Dict[str, Any]) -> Dict[str, bool]:
    palaces = chart["palaces"]
    return {
        role: set(palaces) == set(DIRECTIONS)
        and all(type(palaces[d][role + "_star_number"]) is int for d in DIRECTIONS)
        and sorted(palaces[d][role + "_star_number"] for d in DIRECTIONS)
        == list(range(1, 10))
        and chart[role + "_chart"]
        == {d: palaces[d][role + "_star_number"] for d in DIRECTIONS}
        for role in ROLES
    }


def _compare(
    chart: Dict[str, Any], rows: Dict[tuple[str, int, str], Any]
) -> Dict[str, Any]:
    integrity = _integrity(chart)
    mode = chart["chart_mode"]
    if mode not in ("lower", "replacement"):
        raise ValueError("Unknown computed chart mode cannot receive source agreement")
    result: Dict[str, Any] = {
        "candidate_id": chart["candidate_id"],
        "chart_mode": mode,
        "computed_plate_integrity": integrity,
        "source_section": deepcopy(_bundle()["section_by_mode"][mode]),
        "numeric_branch_only": True,
        "source_angle_applicability_verified": False,
        "star_name_labels_verified": False,
    }
    row = rows[(mode, chart["period_number"], chart["facing"]["name"])]
    if row["sitting_mountain"] != chart["sitting"]["name"]:
        raise ValueError("Computed/source sitting mountain association differs")
    prose_differences = []
    if mode == "lower":
        actual = {
            key: chart["trace"][role][field]
            for role in ("mountain", "facing")
            for key, field in (
                (role + "_seed", "seed_star_number"),
                (role + "_flight", "flight"),
            )
        }
        prose = row["prose"]
        prose_differences = [
            {"field": key, "source_value": value, "computed_value": actual[key]}
            for key, value in prose["numeric_profile"].items()
            if type(actual[key]) is not type(value) or actual[key] != value
        ]
        result["prose"] = {
            **deepcopy(prose),
            "computed_profile": actual,
            "checked_fields": 4,
            "differences": prose_differences,
        }
    diagram = row["diagram"]
    differences = [
        {
            "direction": direction,
            "role": role,
            "source_value": diagram["palaces"][direction][role],
            "computed_value": chart["palaces"][direction][role + "_star_number"],
        }
        for direction in DIRECTIONS
        for role in ROLES
        if type(chart["palaces"][direction][role + "_star_number"]) is not int
        or diagram["palaces"][direction][role]
        != chart["palaces"][direction][role + "_star_number"]
    ]
    agreement = not prose_differences and not differences
    result.update(
        status=(
            "computed_plate_integrity_failure"
            if not all(integrity.values())
            else (
                "selected_numeric_passages_match"
                if agreement
                else "selected_source_difference"
            )
        ),
        local_numeric_agreement=agreement,
        diagram={
            "pdf_page": diagram["pdf_page"],
            "capture_sha256": diagram["capture_sha256"],
            "source_palaces": deepcopy(diagram["palaces"]),
            "checked_numerals": 27,
            "differences": differences,
            "source_plate_permutations": {
                role: sorted(diagram["palaces"][d][role] for d in DIRECTIONS)
                == list(range(1, 10))
                for role in ROLES
            },
        },
    )
    return result


def compare_natal_sources(charts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare all candidates; a literal match never certifies the whole book."""
    data = _bundle()
    rows = {
        (mode, r["period"], r["facing_mountain"]): r
        for mode, field in (("lower", "rows"), ("replacement", "replacement_rows"))
        for r in data[field]
    }
    candidates = [_compare(chart, rows) for chart in charts]
    differences = [
        c["candidate_id"]
        for c in candidates
        if c.get("prose", {}).get("differences")
        or c.get("diagram", {}).get("differences")
    ]
    failed = [
        c["candidate_id"]
        for c in candidates
        if not all(c["computed_plate_integrity"].values())
    ]
    lower_count = sum(c["chart_mode"] == "lower" for c in candidates)
    replacement_count = sum(c["chart_mode"] == "replacement" for c in candidates)
    status = (
        "computed_plate_integrity_failure"
        if failed
        else (
            "selected_source_difference"
            if differences
            else (
                "not_computed" if not candidates else "selected_numeric_passages_match"
            )
        )
    )
    summary = {
        "comparison_ruleset_id": data["ruleset"]["ruleset_id"],
        "comparison_version": data["ruleset"]["version"],
        "status": status,
        "candidate_count": len(candidates),
        "lower_candidates_compared": lower_count,
        "replacement_candidates_compared": replacement_count,
        "replacement_candidates_not_covered": 0,
        "source_angle_applicability_verified": False,
        "difference_candidate_ids": differences,
        "computed_integrity_failure_ids": failed,
        "candidate_results": [
            {
                "candidate_id": c["candidate_id"],
                "status": c["status"],
                "prose_fields_different": (
                    len(c["prose"]["differences"]) if "prose" in c else None
                ),
                "diagram_numerals_different": (
                    len(c["diagram"]["differences"]) if "diagram" in c else None
                ),
            }
            for c in candidates
        ],
        "whole_book_conformity_established": False,
    }
    return {
        "ruleset": comparison_provenance(),
        "summary": summary,
        "candidates": candidates,
        "whole_book_conformity_established": False,
        "independent_human_expert_review_complete": False,
        "calendar_accuracy_verified": False,
        "real_world_prediction_established": False,
        "source_angle_applicability_verified": False,
        "star_name_labels_and_complete_prose_verified": False,
        "scope": "fixed_source_numeric_comparison_not_rule_selection_or_source_correction",
    }


def comparison_statements(comparison: Dict[str, Any]) -> List[tuple[str, str]]:
    """Render the current source comparison without changing its facts."""
    source = comparison["ruleset"]["sources"][0]
    statements = [
        (
            "summary",
            f"原书数表比较：{source['author']}《{source['title']}》，{source['source_version']}。逐候选核对下卦正文四项种子顺逆及27图数；替卦仅核对卷五起星图27数。局部数字相合不认证兼向选盘条件、星名、完整图文、历法精度或现实预测。",
        )
    ]
    role_labels = {"period": "运星", "mountain": "山星", "facing": "向星"}
    field_labels = {
        "mountain_seed": "山星种子",
        "facing_seed": "向星种子",
        "mountain_flight": "山星顺逆",
        "facing_flight": "向星顺逆",
    }
    for index, candidate in enumerate(comparison["candidates"]):
        diagram = candidate["diagram"]
        section = candidate["source_section"]
        text = (
            f"{candidate['candidate_id']}：{section['section']}，{section['author']}。"
        )
        prose = candidate.get("prose")
        if prose is not None:
            text += f"正文4字段差异{len(prose['differences'])}项（PDF{prose['pdf_page']}）；"
            for difference in prose["differences"]:
                a, b = difference["source_value"], difference["computed_value"]
                a = {"forward": "顺", "reverse": "逆"}.get(a, a)
                b = {"forward": "顺", "reverse": "逆"}.get(b, b)
                text += f"{field_labels[difference['field']]}：正文{a}、计算{b}；"
        else:
            text += "本候选仅比较起星图数字，正文未转录核对；"
        text += f"盘图27星数差异{len(diagram['differences'])}项（PDF{diagram['pdf_page']}）。"
        for difference in diagram["differences"]:
            text += f"{difference['direction']}宫{role_labels[difference['role']]}：原图{difference['source_value']}、计算{difference['computed_value']}；"
        invalid_source = [
            role_labels[role]
            for role, valid in diagram["source_plate_permutations"].items()
            if not valid
        ]
        if invalid_source:
            text += "原图" + "、".join(invalid_source) + "存在重复或缺数，原样保留。"
        text += (
            "这是本次数值分支比较，兼向适用条件和星名未验证，不据图数差异推出现实吉凶。"
        )
        if not all(candidate["computed_plate_integrity"].values()):
            text += "本次计算盘未通过九星排列或多份数字表示的一致性检查，不能作为有效盘接受。"
        statements.append((f"candidates.{index}", text))
    if not comparison["candidates"]:
        statements.append(
            (
                "summary",
                "本次尚无计算宅盘候选，原书数表比较未执行，不能把缺少比较当作相合。",
            )
        )
    return statements
