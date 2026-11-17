"""Bounded activity references and explicit entry/barrier relationships."""

from typing import TYPE_CHECKING, Any, Dict, List

from .directions import rule_data
from .natal_interpretation import _ordered_relationship
from .workstation_sources import desktop_reference, provenance

if TYPE_CHECKING:
    from .models import AssessRequest


def _pending(
    path: str, object_id: str, reason: str, required_for: str = "assessment"
) -> Dict[str, Any]:
    return dict(
        path=path, object_id=object_id, reason=reason, required_for=required_for
    )


def analyze_workstation(req: "AssessRequest", layers: Dict[str, Any]) -> Dict[str, Any]:
    review = req.workstation_review
    findings: List[Dict[str, Any]] = []
    missing: List[str] = []
    pending: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    counts = dict(supported=0, confirmed_unsupported=0, unknown=0)
    rules = []
    trace = []
    placements = {p.object_id: p for p in req.placements}
    natal = layers.get("xuankong_natal", {})
    charts = natal.get("candidates", [])
    period = (
        review.evaluation_period.number
        if review.evaluation_period
        else (
            req.xuankong.interpretation.current_period_number
            if req.xuankong and req.xuankong.interpretation
            else None
        )
    )
    elements = {int(k): v["element"] for k, v in rule_data("annual_stars").items()}
    if review.activities:
        rules.append(provenance("workstation_activity_authored_v1"))
    for activity in review.activities:
        path = (
            f"environmental_context.workstation_review.activities.{activity.object_id}"
        )
        record = dict(
            **activity.model_dump(mode="json"),
            rule_id="workstation_activity_authored_v1.wakeful_role",
            source_ids=["K0", "K1", "K2"],
            selected_star_role=None,
            overall_auspiciousness="not_produced",
            scope="activity_role_reference_not_desk_direction_or_water_remedy",
            missing_inputs=[],
        )
        if activity.activity not in {"work", "study"}:
            unknown = activity.activity == "unknown"
            record.update(
                status="needs_confirmation" if unknown else "unsupported",
                coverage_reason=(
                    "unknown_activity" if unknown else "activity_rule_not_implemented"
                ),
                action_options=[],
            )
            if unknown:
                record["missing_inputs"].append(path + ".activity")
                pending.append(
                    _pending(
                        path + ".activity",
                        activity.object_id,
                        "confirm_actual_activity",
                    )
                )
            counts["unknown" if unknown else "confirmed_unsupported"] += 1
            findings.append(record)
            missing.extend(record["missing_inputs"])
            continue
        record["selected_star_role"] = "facing"
        record["reference_finding"] = "authored_wakeful_role"
        placement = placements.get(activity.object_id)
        location = placement.location_direction if placement else None
        if activity.observation_basis == "image_observed":
            record["missing_inputs"].append(path + ".observation_basis")
        if location is None:
            record["missing_inputs"].append(
                f"placements.{activity.object_id}.location_direction"
            )
        if not charts:
            record["missing_inputs"].append(
                "workstation_review.computed_xuankong_natal"
            )
        if len(charts) > 1:
            record["missing_inputs"].append("xuankong_natal.unambiguous_bearing")
        record.update(
            status=(
                "candidate_only"
                if record["missing_inputs"]
                else "role_reference_available"
            ),
            coverage_reason=(
                "factual_or_chart_uncertainty"
                if record["missing_inputs"]
                else "authored_activity_reference"
            ),
            location_direction=location,
            mixed_use_review=(
                activity.space_mixed_use.model_dump(mode="json")
                if activity.space_mixed_use
                else None
            ),
            mixed_use_policy="retain_other_activities_no_combined_room_verdict",
            candidates=[],
        )
        for chart in charts:
            palace = chart["palaces"].get(location) if location else None
            if palace is None:
                continue
            number = palace["facing_star_number"]
            mountain = palace["mountain_star_number"]
            pair = dict(
                rule_id="workstation_activity_authored_v1.ordered_pair",
                source_ids=["K2", "A3"],
                mountain_star_number=mountain,
                facing_star_number=number,
                mountain_element=elements[mountain],
                facing_element=elements[number],
                relationship=_ordered_relationship(
                    elements[mountain], elements[number]
                ),
                verdict_scope="directed_element_relationship_only_no_81_pair_fortune_judgment",
            )
            record["candidates"].append(
                dict(
                    candidate_id=chart["candidate_id"],
                    candidate_only=len(charts) > 1
                    or activity.observation_basis == "image_observed",
                    natal_period_number=chart["period_number"],
                    selected_star_number=number,
                    star_element=elements[number],
                    mountain_star_number=palace["mountain_star_number"],
                    ordered_pair=pair,
                    current_period_number=period,
                    timeliness=(
                        "unknown"
                        if period is None
                        else "current" if period == number else "not_current"
                    ),
                    external_form_assessment="independent_not_required_to_explain_activity_role",
                    non_current_policy="not_current_is_not_inauspicious",
                    overall_auspiciousness="not_produced",
                )
            )
            trace.append(
                dict(
                    rule_id=pair["rule_id"],
                    source_ids=pair["source_ids"],
                    object_id=activity.object_id,
                    candidate_id=chart["candidate_id"],
                    evidence=dict(
                        mountain_star_number=mountain, facing_star_number=number
                    ),
                )
            )
        for key in record["missing_inputs"]:
            pending.append(
                _pending(
                    key,
                    activity.object_id,
                    "confirm_only_if_needed_for_requested_activity_reference",
                )
            )
        counts["unknown" if record["missing_inputs"] else "supported"] += 1
        missing.extend(record["missing_inputs"])
        findings.append(record)

    constraints = {c.object_id: c for c in req.layout_constraints}
    if review.entry_barriers:
        rules.append(provenance("afsi_entry_barrier_v1"))
    for relation in review.entry_barriers:
        path = f"environmental_context.workstation_review.entry_barriers.{relation.relation_id}"
        line = relation.entry_line_through_user
        between = relation.barrier_between_entry_and_user
        relevant_facts = (
            (line,)
            if line.value is False and line.observation_basis != "image_observed"
            else (line, between)
        )
        uncertain = relation.observation_basis == "image_observed" or any(
            f.value is None or f.observation_basis == "image_observed"
            for f in relevant_facts
        )
        record = dict(
            **relation.model_dump(mode="json"),
            rule_id="afsi_entry_barrier_v1.entry_line_barrier",
            source_ids=["A1"],
            status=(
                "candidate_only"
                if uncertain
                else "not_indicated" if line.value is False else "relationship_reviewed"
            ),
            scope="specific_entry_user_barrier_relationship_no_lucky_side",
            present=line.value,
            method_disagreements=[],
            missing_inputs=[],
            action_options=[],
        )
        for key in ("entry_line_through_user", "barrier_between_entry_and_user"):
            if key == "barrier_between_entry_and_user" and len(relevant_facts) == 1:
                continue
            fact = getattr(relation, key)
            if fact.value is None or fact.observation_basis == "image_observed":
                record["missing_inputs"].append(path + "." + key)
                pending.append(
                    _pending(
                        path + "." + key,
                        relation.desk_id,
                        "confirm_entry_barrier_relationship",
                    )
                )
        if relation.observation_basis == "image_observed":
            record["missing_inputs"].append(path + ".observation_basis")
            pending.append(
                _pending(
                    path + ".observation_basis",
                    relation.barrier_id,
                    "confirm_barrier_identity",
                )
            )
        counts["unknown" if uncertain else "supported"] += 1
        if line.value is not False:
            constraint = constraints.get(
                relation.desk_id if relation.operation == "add" else relation.barrier_id
            )
            permission_field = (
                "can_add_items" if relation.operation == "add" else "can_relocate"
            )
            permission = (
                True
                if relation.operation == "retain"
                else getattr(constraint, permission_field) if constraint else None
            )
            execution = [
                "entrance_view_maintained",
                "circulation_clear",
                "operating_space_clear",
                "physically_feasible",
            ]
            blocked = (
                permission is False
                or (
                    relation.operation == "retain"
                    and between.value is False
                    and between.observation_basis != "image_observed"
                )
                or any(
                    getattr(relation, k) is not None
                    and getattr(relation, k).value is False
                    and getattr(relation, k).observation_basis != "image_observed"
                    for k in execution
                )
            )
            needs = []
            if permission is not True:
                needs.append(
                    _pending(
                        f"layout_constraints.{relation.desk_id if relation.operation == 'add' else relation.barrier_id}.{permission_field}",
                        relation.barrier_id,
                        "confirm_action_permission",
                        "optional_action",
                    )
                )
            if (
                between.value is not True
                or between.observation_basis == "image_observed"
            ):
                needs.append(
                    _pending(
                        path + ".barrier_between_entry_and_user",
                        relation.barrier_id,
                        "verify_actual_interposition",
                        "optional_action",
                    )
                )
            for key in execution:
                fact = getattr(relation, key)
                if (
                    fact is None
                    or fact.value is not True
                    or fact.observation_basis == "image_observed"
                ):
                    needs.append(
                        _pending(
                            path + "." + key,
                            relation.barrier_id,
                            "verify_engineering_execution_condition",
                            "optional_action",
                        )
                    )
            action = dict(
                action_id=f"entry-barrier:{relation.relation_id}",
                object_id=relation.barrier_id,
                operation=relation.operation,
                status=(
                    "blocked"
                    if blocked
                    else (
                        "candidate_only"
                        if uncertain
                        else "conditional_option" if needs else "ready"
                    )
                ),
                optional=True,
                blocking_reasons=(
                    (["action_permission_denied"] if permission is False else [])
                    + (
                        ["retained_barrier_not_between_entry_and_user"]
                        if relation.operation == "retain"
                        and between.value is False
                        and between.observation_basis != "image_observed"
                        else []
                    )
                    + [
                        key + "_not_met"
                        for key in execution
                        if getattr(relation, key) is not None
                        and getattr(relation, key).value is False
                        and getattr(relation, key).observation_basis != "image_observed"
                    ]
                ),
                pending_confirmations=[] if blocked else needs,
                rule_id=record["rule_id"],
                source_ids=["A1"],
                action_basis="authored_barrier_option_with_separate_engineering_conditions",
                placement_direction="not_prescribed",
                efficacy="not_established",
            )
            record["action_options"].append(action)
            actions.append(action)
            pending.extend(action["pending_confirmations"])
        findings.append(record)
        missing.extend(record["missing_inputs"])
    for record in findings:
        trace.append(
            dict(
                rule_id=record["rule_id"],
                source_ids=record["source_ids"],
                object_id=record.get("object_id", record.get("desk_id")),
                status=record["status"],
            )
        )
    return dict(
        status="partial" if missing else "complete",
        findings=findings,
        missing_inputs=list(dict.fromkeys(missing)),
        rulesets=rules,
        rule_trace=trace,
        rule_coverage_counts=counts,
        action_options=actions,
        pending_confirmations=pending,
        non_btb_desktop_reference=desktop_reference(),
        evaluation_period_context=dict(
            number=period,
            source=(
                "explicit_review"
                if review.evaluation_period
                else (
                    "explicit_existing_interpretation"
                    if period is not None
                    else "not_provided"
                )
            ),
            natal_period_independent=True,
        ),
        limitations=["作者用途、物件关系与实际效力分别说明；不产生总分或固定吉位"],
    )
