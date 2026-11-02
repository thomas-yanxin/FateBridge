"""Compare exposed source annotations without changing any computed grade."""

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from fatebridge.core.source_conditions import condition_reviews
from fatebridge.core.source_identity import (
    NAME_NOTE,
    PUBLISHER_NOTE,
    validate_identity_index,
)

ORDER = ("year", "month", "day", "hour")
GRADES = {"强", "中和", "弱"}


@lru_cache(maxsize=1)
def _index() -> Tuple[Dict[tuple, list], Dict[str, Any]]:
    path = (
        Path(__file__).resolve().parents[1]
        / "data/reference/bazi-source-annotations-v8.json"
    )
    raw = path.read_bytes()
    data = json.loads(raw)
    identity_data = deepcopy(data)
    if data["schema_version"] != 1 or len(data["records"]) != data["record_count"]:
        raise ValueError("原典参考索引结构或记录数不一致")
    grouped: Dict[tuple, list] = {}
    records_by_id = {r["reference_id"]: r for r in data["records"]}
    if len(records_by_id) != len(data["records"]):
        raise ValueError("原典参考编号重复")
    constraints = data["strength_constraints"]
    if len(constraints) != data["strength_constraint_count"]:
        raise ValueError("原典集合约束数不一致")
    if len({c["constraint_id"] for c in constraints}) != len(constraints):
        raise ValueError("原典集合约束编号重复")
    for constraint in constraints:
        record = records_by_id[constraint["reference_id"]]
        record.setdefault("bounded_strength_constraints", []).append(constraint)
    for record in data["records"]:
        if record["retained_strength_annotation"] not in GRADES | {None}:
            raise ValueError("原典参考含未登记的强弱编释")
        grouped.setdefault(tuple(record["pillars"]), []).append(record)
    revisions = [r for r in data["records"] if "input_reading_revision" in r]
    if len(revisions) != data["input_reading_revision_count"]:
        raise ValueError("原典输入校读修订数不一致")
    for record in revisions:
        revision = record["input_reading_revision"]
        original = revision["original_index_record"]
        if (
            original["reference_id"] != record["reference_id"]
            or original["retained_strength_annotation"] is not None
            or record["retained_strength_annotation"] is not None
            or revision["source_strength_label_assigned"] is not False
            or revision["new_independent_validation_credit"] != 0
        ):
            raise ValueError("输入校读不得改写原典等级或增加独立验证信用")
    notes = [r for r in data["records"] if "editorial_annotation_provenance" in r]
    if len(notes) != data["editorial_annotation_count"]:
        raise ValueError("登记编辑说明投影数不一致")
    for record in notes:
        provenance = record["editorial_annotation_provenance"]
        if (
            provenance["content_kind"] != "registered_editorial_annotation"
            or provenance["case_id"] != record["case_id"]
            or provenance["is_verbatim_original_text"] is not False
            or provenance["strength_label_assigned_or_regraded"] is not False
            or provenance["new_independent_validation_credit"] != 0
            or provenance["previous_strength_annotation"]
            != record["retained_strength_annotation"]
            or provenance["registered_document"]
            != record["source_reference"]["registered_document"]
            or provenance["registered_document_sha256"]
            != record["source_reference"]["registered_document_sha256"]
            or record["annotation_basis"] != record["retained_context"]
            or hashlib.sha256(record["annotation_basis"].encode()).hexdigest()
            != provenance["annotation_sha256"]
        ):
            raise ValueError("编辑说明不得冒充原典引文、重判标签或丢失原说明")
    if len(grouped) != data["literal_input_count"]:
        raise ValueError("原典参考字面输入数不一致")
    validate_identity_index(identity_data, path.parent)
    reviews, condition_metadata = condition_reviews(
        identity_data, path.parent, hashlib.sha256(raw).hexdigest()
    )
    for record in data["records"]:
        if record["reference_id"] in reviews:
            record["source_condition_review"] = reviews[record["reference_id"]]
    metadata = {
        **condition_metadata,
        "method_id": data["method_id"],
        "index_sha256": hashlib.sha256(raw).hexdigest(),
        "registry_sha256": data["registry_sha256"],
        "total_registered_records": data["record_count"],
        "total_registered_literal_inputs": data["literal_input_count"],
        "total_registered_strength_constraints": len(constraints),
        "all_records_previously_exposed": True,
        "total_registered_input_reading_revisions": len(revisions),
        "input_reading_plan_sha256": data["input_reading_plan_sha256"],
        "data_revision": data["data_revision"],
        "total_registered_editorial_annotations": len(notes),
        "editorial_annotation_projection_sha256": data[
            "editorial_annotation_projection_sha256"
        ],
        "source_identity_plan_sha256": data["source_identity_plan_sha256"],
        "total_registered_source_identity_revisions": data[
            "source_identity_revision_count"
        ],
        "total_registered_printed_name_corrections": data[
            "source_identity_name_revision_count"
        ],
    }
    return grouped, metadata


def compare_strength_bounds(
    records: list, computed_strength: Optional[str]
) -> Dict[str, Any]:
    """Evaluate exclusions independently of exact source grades and preserve conflicts."""
    claims = []
    remaining = set(GRADES)
    expected = {r["retained_strength_annotation"] for r in records} - {None}
    for record in records:
        for claim in record.get("bounded_strength_constraints", []):
            claim = deepcopy(claim)
            forbidden = claim["forbidden_strengths"]
            if (
                not isinstance(forbidden, list)
                or not forbidden
                or any(not isinstance(v, str) or v not in GRADES for v in forbidden)
            ):
                raise ValueError("原典集合约束必须保留明确有效的禁止等级")
            remaining -= set(forbidden)
            claim["comparison"] = (
                "current_grade_missing"
                if computed_strength is None
                else "violates" if computed_strength in forbidden else "satisfies"
            )
            claims.append(claim)
    conflict_with_exact = any(
        grade in claim["forbidden_strengths"] for grade in expected for claim in claims
    )
    status = (
        "no_registered_bounds"
        if not claims
        else (
            "contradictory_registered_bounds"
            if not remaining
            else (
                "current_grade_missing"
                if computed_strength is None
                else (
                    "violates_registered_bounds"
                    if any(c["comparison"] == "violates" for c in claims)
                    else "satisfies_registered_bounds"
                )
            )
        )
    )
    return {
        "status": status,
        "claim_count": len(claims),
        "satisfied_count": sum(c["comparison"] == "satisfies" for c in claims),
        "violated_count": sum(c["comparison"] == "violates" for c in claims),
        "uncompared_count": sum(
            c["comparison"] == "current_grade_missing" for c in claims
        ),
        "remaining_strengths_under_all_bounds": sorted(remaining) if claims else [],
        "conflicts_with_retained_exact_annotations": conflict_with_exact,
        "claims": claims,
        "exact_strength_label_assigned": False,
        "new_independent_validation_credit": 0,
        "scope": "集合约束单独核对，不把未违反约束计为三档标签相符；不覆盖计算，不认证原典或预测效度。",
    }


def compare_records(records: list, computed_strength: Optional[str]) -> Dict[str, Any]:
    """Keep conflicting and unknown annotations; a match never certifies a book."""
    if computed_strength not in GRADES | {None}:
        raise ValueError("当前强弱必须为强、中和、弱或明确未提供")
    rows = deepcopy(records)
    expected = {r["retained_strength_annotation"] for r in rows} - {None}
    known = [r for r in rows if r["retained_strength_annotation"] is not None]
    for row in rows:
        grade = row["retained_strength_annotation"]
        row["comparison"] = (
            "unadjudicated"
            if grade is None
            else (
                "current_grade_missing"
                if computed_strength is None
                else "agrees" if grade == computed_strength else "differs"
            )
        )
    if not rows:
        status = "no_registered_literal_case"
    elif len(expected) > 1:
        status = "conflicting_registered_annotations"
    elif not known:
        status = "unadjudicated_records_only"
    elif computed_strength is None:
        status = "current_grade_missing"
    elif any(r["comparison"] == "differs" for r in rows):
        status = "known_annotation_mismatch"
    else:
        status = "agrees_with_known_annotations"
    return {
        "status": status,
        "computed_strength": computed_strength,
        "literal_match_count": len(rows),
        "known_annotation_count": len(known),
        "unknown_or_unannotated_count": len(rows) - len(known),
        "agreeing_known_count": sum(r["comparison"] == "agrees" for r in rows),
        "differing_known_count": sum(r["comparison"] == "differs" for r in rows),
        "retained_expected_strengths": sorted(expected),
        "records": rows,
        "bounded_comparison": compare_strength_bounds(rows, computed_strength),
        "calculation_overridden": False,
        "exact_literal_match_only": True,
        "independent_annotation_review": "not_certified",
        "full_original_text_conformance_certified": False,
        "historical_identity_asserted": False,
        "new_independent_validation_credit": 0,
        "scope": "仅核对已暴露字面四柱与保留编释；不是全书认证、独立外审、同一历史人物认定或预测验证。无条目、未知与相符均不认证完整原典，计算结果不由参考标签改写。",
    }


def compare_registered_annotations(
    pillars: Mapping[str, Tuple[str, str]], computed_strength: Optional[str]
) -> Dict[str, Any]:
    index, metadata = _index()
    key = tuple("".join(pillars[p]) for p in ORDER)
    return {
        **compare_records(index.get(key, []), computed_strength),
        "reference_index": dict(metadata),
    }


def _exact_annotation_comparison_summary(comparison: Mapping[str, Any]) -> str:
    current = comparison["computed_strength"] or "未提供"
    status = comparison["status"]
    if status == "no_registered_literal_case":
        return f"当前模型判{current}；未发现已登记同四柱记录，原典符合度未核实。"
    if status == "unadjudicated_records_only":
        return (
            f"当前模型判{current}；同柱参考未裁定日主三档强弱，不能据此认证原典符合。"
        )
    labels = "、".join(comparison["retained_expected_strengths"])
    if status == "conflicting_registered_annotations":
        return f"当前模型判{current}；保留标注有{labels}等不同意见，不能只选相符记录。"
    if status == "known_annotation_mismatch":
        return f"当前模型判{current}，同柱保留编释为{labels}，存在已知差异；未改写计算，原典符合仍未认证。"
    if status == "current_grade_missing":
        return f"当前计算未提供强弱；同柱保留编释为{labels}，尚不能比较。"
    return f"当前模型判{current}，与已知同柱编释相符；另有{comparison['unknown_or_unannotated_count']}条未裁定，有限相符不认证完整原典。"


def annotation_comparison_summary(comparison: Mapping[str, Any]) -> str:
    summary = _exact_annotation_comparison_summary(comparison)
    if any("source_identity_revision" in r for r in comparison["records"]):
        summary += PUBLISHER_NOTE
    if any("name_as_printed" in r for r in comparison["records"]):
        summary += NAME_NOTE
    if any("editorial_annotation_provenance" in r for r in comparison["records"]):
        summary += "已附登记编辑说明，须与原典引文分开；说明未重判强弱。"
    revisions = sum("input_reading_revision" in r for r in comparison["records"])
    if revisions:
        summary += (
            f"其中{revisions}条参考输入已按图版校读修订，原录文与修订依据均保留；"
            "校读未补定强弱标签。"
        )
    bounds = comparison.get("bounded_comparison", {})
    if not bounds.get("claim_count"):
        return summary
    if bounds["status"] == "contradictory_registered_bounds":
        suffix = "保留的集合约束彼此冲突，未选择性舍弃。"
    elif bounds["status"] == "current_grade_missing":
        suffix = "原典另有集合约束，当前等级缺失，尚不能核对。"
    elif bounds["violated_count"]:
        suffix = f"另有{bounds['violated_count']}条原典集合约束被当前计算违反；不能以未裁定三档标签掩盖该差异。"
    else:
        suffix = "当前计算未违反已登记集合约束；这不等于已确定原典三档强弱。"
    if bounds["conflicts_with_retained_exact_annotations"]:
        suffix += "集合约束与保留三档编释也有冲突，均已保留。"
    return summary + suffix
