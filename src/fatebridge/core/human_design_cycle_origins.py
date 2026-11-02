"""Conditional Design-origin sensitivity, without changing selected cycles.

The Design epoch is the actual 88-degree solar-arc root, not an inferred
biological date. This comparison does not establish an original-text rule.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from fatebridge.core.human_design_cycle_sources import CycleBirthSources
from fatebridge.core.human_design_cycles import (
    BODIES,
    HORIZON_DAYS,
    STEP_DAYS,
    CycleUnavailable,
    _native_reader,
    attach_contact_labels,
    cycle_ruleset,
    derive_body_contacts,
    origin_source_evidence,
    reference_contact_relation,
)
from fatebridge.utils.errors import EphemerisSourceError

METHOD = "human_design_design_origin_sensitivity_v1"
ALTERNATIVE_METHOD = "human_design_design_epoch_first_cycle_contacts_v1"
SCOPE = "主结果仍按人格出生原点；另从实际88度太阳弧设计TT起算同一65儒略年有限搜索。设计原点只是假设，不推定生物学日期或原典优先；各原点保留全部已观察交会及失败，不按序号配对不同数量的交会，不指定首末触传统取舍或当前阶段。不认证连续穷尽、物理时刻精度、完整原典或预测效力。"
ALTERNATIVE_SCOPE = "从本盘实际设计TT展开黄经，有限搜索该原点起65儒略年的首轮360度回归或180度对冲；沿用原2日网格、速度驻点与有限坐标极值探查及全部数值见证。该假设没有被提升为传统原点，也不是出生时刻或生物学日期。"
SUMMARY_SCOPE = "人格主结果与设计原点假设的有限候选比较；首末差值只比较各自已观察集合端点，不配对全部交会，不认证物理误差或分配传统阶段。"


def origin_body_row(row: dict[str, Any]) -> dict[str, Any]:
    """Expose an origin without relabelling the Design instant as a birth."""
    return {
        **{k: v for k, v in row.items() if k not in {"birth_jd_tt", "natal_longitude"}},
        "origin_jd_tt": row["birth_jd_tt"],
        "origin_longitude": row["natal_longitude"],
    }


def alternative_context(
    origin_tt: float, rows: list[dict[str, Any]], source: dict[str, Any], policy: bool
) -> dict[str, Any]:
    return {
        "method_id": ALTERNATIVE_METHOD,
        "origin_side": "design",
        "origin_jd_tt": origin_tt,
        "status": (
            "computed_finite_search"
            if all(r["status"] == "sampled_search_completed" for r in rows)
            else "partial"
        ),
        "step_days_tt": STEP_DAYS,
        "horizon_days_tt": HORIZON_DAYS,
        "require_swiss_files": policy,
        "ruleset": cycle_ruleset(),
        "bodies": rows,
        "source_evidence": source,
        "continuous_completeness_certified": False,
        "timing_accuracy_certified": False,
        "scope": ALTERNATIVE_SCOPE,
    }


def _endpoints(row: dict[str, Any], reference: Fraction) -> dict[str, Any]:
    keys = (
        "jd_tt",
        "utc_label",
        "utc_label_status",
        "future_leap_seconds_assumed_unchanged",
        "bracket_jd_tt",
        "motion",
    )
    contacts = row["contacts"]
    return {
        "status": row["status"],
        "failure": row["failure"],
        "observed_contact_count": len(contacts),
        "reference_relation": reference_contact_relation(row, reference),
        "first_observed_contact": (
            {k: contacts[0][k] for k in keys} if contacts else None
        ),
        "last_observed_contact": (
            {k: contacts[-1][k] for k in keys} if contacts else None
        ),
    }


def comparison_rows(
    primary: list[dict[str, Any]],
    alternative: list[dict[str, Any]],
    reference: Fraction,
) -> list[dict[str, Any]]:
    result = []
    if [r["body"] for r in primary] != list(BODIES) or [
        r["body"] for r in alternative
    ] != list(BODIES):
        raise ValueError("Cycle origin comparison requires all three ordered bodies")
    for selected, assumed in zip(primary, alternative, strict=True):
        a, b = _endpoints(selected, reference), _endpoints(assumed, reference)
        shifts = {}
        for endpoint in ("first", "last"):
            key = endpoint + "_observed_contact"
            shifts[endpoint + "_observed_shift_seconds"] = (
                float((Fraction(b[key]["jd_tt"]) - Fraction(a[key]["jd_tt"])) * 86400)
                if a[key] is not None and b[key] is not None
                else None
            )
        result.append(
            {
                "body": selected["body"],
                "selected_personality": a,
                "design_hypothesis": b,
                **shifts,
                "chronological_contact_pairing_assumed": False,
            }
        )
    return result


def origin_reading(rows: list[dict[str, Any]]) -> str:
    text = "人格出生原点的周期主结果保持；设计原点仅作来源未决条件下的数学敏感性对照。"
    names = {"Saturn": "土星", "Uranus": "天王星", "Chiron": "凯龙星"}
    for row in rows:
        a, b = row["selected_personality"], row["design_hypothesis"]
        text += f"{names[row['body']]}已观察交会：人格原点{a['observed_contact_count']}次，设计假设{b['observed_contact_count']}次。"
        for endpoint, label in (("first", "首个"), ("last", "末个")):
            value = row[endpoint + "_observed_shift_seconds"]
            text += (
                f"两集合{label}候选的设计减人格TT数值差为{value:.3f}秒。"
                if value is not None
                else f"{label}候选缺少双侧见证，差值未知。"
            )
        if any(x["status"] != "sampled_search_completed" for x in (a, b)):
            text += "至少一侧搜索未完成，参考位置保持未评估，不由零个已观察候选推断没有交会。"
    return (
        text
        + "天王星出生原点有公开明文；设计假设不是同等原典依据。土星／凯龙原点及全部首末触优先仍未裁定，不据此分配第六线阶段或预测事件。"
    )


def assemble_origin_comparison(
    chart: dict[str, Any], primary: dict[str, Any], alternative: dict[str, Any]
) -> dict[str, Any]:
    ratio = primary["reference_ordering"]["reference"]["exact_jd_tt"]
    reference = Fraction(int(ratio["numerator"]), int(ratio["denominator"]))
    rows = comparison_rows(primary["bodies"], alternative["bodies"], reference)
    design = chart["time_scales"]["design"]["jd_tt"]
    personality = chart["time_scales"]["personality"]["jd_tt"]
    return {
        "method_id": METHOD,
        "ruleset": {
            "id": METHOD,
            "version": "1.0.0",
            "author": "FateBridge conditional calculation",
        },
        "requested": True,
        "status": (
            "computed_finite_comparison"
            if primary["status"] == alternative["status"] == "computed_finite_search"
            else "partial"
        ),
        "selected_context_path": "cycle_context",
        "selected_origin": {
            "side": "personality",
            "jd_tt": personality,
            "utc_label": chart["birth_utc"],
        },
        "hypothesis_origin": {
            "side": "design",
            "jd_tt": design,
            "utc_label": chart["design_utc"],
            "biological_date_inferred": False,
            "source_preferred": False,
        },
        "origin_position_bindings": {
            body: f"activations.design.{next(i for i, a in enumerate(chart['activations']['design']) if a['body'] == body)}"
            for body in ("Saturn", "Uranus")
        },
        "source_conventions": [
            {
                "body": body,
                "selected_origin_evidence": origin_source_evidence(body),
                "design_origin_status": "counterfactual_not_original_text_preferred",
            }
            for body in BODIES
        ],
        "reference_utc": primary["reference_utc"],
        "reference_jd_tt": primary["reference_jd_tt"],
        "reference_exact_jd_tt": ratio,
        "alternative": alternative,
        "summary": {
            "bodies": rows,
            "current_traditional_phase": None,
            "source_disagreement_resolved": False,
            "physical_timing_accuracy_certified": False,
            "scope": SUMMARY_SCOPE,
        },
        "interpretation": origin_reading(rows),
        "first_last_priority_assigned": False,
        "source_disagreement_resolved": False,
        "continuous_completeness_certified": False,
        "physical_timing_accuracy_certified": False,
        "scope": SCOPE,
    }


def calculate_origin_comparison(
    chart: dict[str, Any],
    primary: dict[str, Any],
    *,
    require_swiss_files: bool,
    origin_sources: CycleBirthSources,
) -> dict[str, Any]:
    origin = chart["time_scales"]["design"]["jd_tt"]
    if origin_sources.jd_tt != origin or set(origin_sources.rows) != {
        "Saturn",
        "Uranus",
    }:
        raise EphemerisSourceError("design_origin_source_mismatch")
    traces: dict[str, dict[float, list[float | int]]] = {b: {} for b in BODIES}
    indices: dict[str, dict[float, int]] = {b: {} for b in BODIES}
    failures: dict[str, dict[float, str]] = {b: {} for b in BODIES}
    for body, seed in origin_sources.rows.items():
        activation = next(
            a for a in chart["activations"]["design"] if a["body"] == body
        )
        if seed != [
            origin,
            activation["longitude"],
            activation["longitude_speed"],
            activation["return_flags"],
        ]:
            raise EphemerisSourceError("design_origin_source_mismatch")
        traces[body][origin] = list(seed)
        indices[body][origin] = origin_sources.indices[body]
    readers = {
        body: _native_reader(
            body,
            require_swiss_files,
            traces[body],
            failures[body],
            source_trace=origin_sources.trace,
            source_indices=indices[body],
        )
        for body in BODIES
    }
    for body in BODIES:
        try:
            readers[body](origin)
        except CycleUnavailable:
            pass
    rows = []
    for body in BODIES:
        row = derive_body_contacts(
            body, origin, readers[body], require_swiss_files=require_swiss_files
        )
        attach_contact_labels(row)
        row["evaluation_witnesses"] = [traces[body][t] for t in sorted(traces[body])]
        row["evaluation_source_context_indices"] = [
            indices[body][t] for t in sorted(traces[body])
        ]
        row["unavailable_evaluations"] = [
            {"jd_tt": t, "reason": reason}
            for t, reason in sorted(failures[body].items())
        ]
        rows.append(origin_body_row(row))
    alternative = alternative_context(
        origin, rows, origin_sources.trace.finish(), require_swiss_files
    )
    return assemble_origin_comparison(chart, primary, alternative)
