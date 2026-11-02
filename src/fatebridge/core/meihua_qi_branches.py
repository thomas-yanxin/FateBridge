"""Literal time-unit branch atoms, with separate actual input label bases."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_roles import LABELS

from ..utils.data import EARTHLY_BRANCHES
from .meihua_qi_days import chapter_timing_targets, qi_day_atom_ruleset

UNITS = ("year", "month", "day", "hour")
UNIT_NAMES = {"year": "年", "month": "月", "day": "日", "hour": "时"}


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/qi-branch-units-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        value["id"] != "meihua_qi_branch_units_nlc1925_v1"
        or value["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected time-unit branch profile")
    if (
        set(value["unit_branch_atoms"]) != set("乾坤震巽坎离艮兑")
        or value["chapter_selectors"] != qi_day_atom_ruleset()["chapter_selectors"]
    ):
        raise ValueError(
            "Time-unit atoms must retain the selected original chapter roles"
        )
    for row in value["unit_branch_atoms"].values():
        if set(row["unit_branches"]) != set(UNITS):
            raise ValueError("Each source atom requires all four separate units")
        for branches in row["unit_branches"].values():
            if (
                not branches
                or len(branches) != len(set(branches))
                or any(b not in EARTHLY_BRANCHES for b in branches)
            ):
                raise ValueError(
                    "Source time units require explicit named branch labels"
                )
    return value


def qi_branch_unit_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _label(
    identifier: str,
    branch: str,
    *,
    path: str,
    basis: str,
    origin: str,
    **qualifiers: Any,
) -> dict[str, Any]:
    if branch not in EARTHLY_BRANCHES:
        raise ValueError("A known time-unit label must be an actual input branch")
    return {
        "id": identifier,
        "branch": branch,
        "branch_fact_path": path,
        "basis": basis,
        "origin": origin,
        **qualifiers,
    }


def _input_labels(
    original: dict[str, Any],
    cast: dict[str, Any],
    layer: dict[str, Any],
    roles: dict[str, dict[str, Any]],
    *,
    fact_prefix: str,
    layer_path: str,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {unit: [] for unit in UNITS}
    seed, policy = original["seed"], original["calendar_policy"]
    parameters = seed.get("parameters", {})
    if parameters.get("method") == "lunar_time_added_count":
        year = parameters["year_branch"]
        year_path = "meihua.seed.parameters.year_branch"
        origin = "caller_confirmed_lunar_labels_unverified"
        month = parameters["lunar_month"]
        month_path = "meihua.seed.parameters.lunar_month"
    else:
        year = seed.get("year_branch")
        year_path = "meihua.seed.year_branch"
        origin = "computed_selected_lunar_clock_labels"
        month = seed.get("lunar_month")
        month_path = "meihua.seed.lunar_month"
    if year is not None:
        result["year"].append(
            _label(
                "original_lunar_year",
                year,
                path=year_path,
                basis="original_cast_lunar_year_not_zi_day_alternative_or_lichun_year",
                origin=origin,
                year_boundary=policy.get("year_boundary"),
                absolute_lunar_year=policy.get("lunar_year"),
            )
        )
    hour = seed.get("hour_branch")
    if hour is not None:
        if parameters and parameters.get("hour_branch") != hour:
            raise ValueError("Time-unit hour must remain the original declared hour")
        result["hour"].append(
            _label(
                "original_hour",
                hour,
                path="meihua.seed.hour_branch",
                basis=policy["hour_basis"],
                origin="original_computed_or_declared_hour_not_recast",
            )
        )
    seasonal = (
        cast.get("seasonal_strength")
        if fact_prefix == "meihua"
        else layer.get("seasonal_strength")
    )
    parent_seasonal = original.get("seasonal_strength")
    if (seasonal is None) != (parent_seasonal is None):
        raise ValueError("Each candidate must retain the same original month input")
    if seasonal is not None and (
        parent_seasonal is None
        or seasonal["month_branch"] != parent_seasonal["month_branch"]
    ):
        raise ValueError("Each candidate must retain the same original month input")
    if seasonal is not None:
        prefix = (
            fact_prefix + ".seasonal_strength"
            if fact_prefix == "meihua"
            else layer_path + ".seasonal_strength"
        )
        result["month"].append(
            _label(
                "seasonal_jie_month",
                seasonal["month_branch"],
                path=prefix + ".month_branch",
                basis=seasonal["basis"],
                origin="existing_declared_or_computed_seasonal_month_input",
                used_by_existing_strength_layer=True,
                uniquely_selected_for_source_timing=False,
            )
        )
    if month is not None:
        if type(month) is not int or not 1 <= month <= 12:
            raise ValueError("Nominal month label requires an existing month number")
        result["month"].append(
            _label(
                "nominal_lunar_month",
                _profile()["nominal_month_labels"][str(month)],
                path=layer_path
                + (".topic_reading" if fact_prefix == "meihua" else ".topic_clause")
                + f".qi_branch_timing_reference.input_unit_labels.month.{len(result['month'])}.branch",
                basis="hko_numbered_month_branch_table_nominal_label_only",
                origin=origin,
                source_value_kind="derived_branch_label_from_nominal_month_number",
                nominal_lunar_month_fact_path=month_path,
                nominal_lunar_month=month,
                is_leap_month=policy.get("is_leap_month"),
                leap_month_scope="repeat_nominal_number_label_only_not_full_leap_month_ganzhi_adjudication",
                used_by_existing_cast_month_count=True,
                uniquely_selected_for_source_timing=False,
                mapping_source=deepcopy(_profile()["nominal_month_label_source"]),
            )
        )
    day = layer.get("day_qi")
    if day is not None:
        calendars = day["calendar_candidates"]
        if (
            sum(c["calendar"]["id"] == day["selected_candidate_id"] for c in calendars)
            != 1
        ):
            raise ValueError(
                "Time-unit day labels require the original selected candidate"
            )
        for i, row in enumerate(calendars):
            if [r["role"] for r in row["roles"]] != list(roles):
                raise ValueError("Input day must retain each candidate's actual roles")
            for r in row["roles"]:
                if (r["trigram"], r["fact_path"]) != (
                    roles[r["role"]]["trigram"],
                    roles[r["role"]]["fact_path"],
                ):
                    raise ValueError("Time-unit day cannot borrow another cast's body")
            c = row["calendar"]
            if c["ganzhi"] is not None and c["ganzhi"][1] != c["day_branch"]:
                raise ValueError("Input day branch and its ganzhi label disagree")
            result["day"].append(
                _label(
                    c["id"],
                    c["day_branch"],
                    path=row["day_branch_fact_path"],
                    basis=c["day_boundary"],
                    origin=day["origin"],
                    queried_date=c["date"],
                    selected_by_existing_day_convention=c["id"]
                    == day["selected_candidate_id"],
                    calendar_record_fact_path=f"{layer_path}.day_qi.calendar_candidates.{i}.calendar",
                    changes_other_units=False,
                )
            )
    return result


def _reading(
    original: dict[str, Any],
    cast: dict[str, Any],
    layer: dict[str, Any],
    topic: str,
    *,
    fact_prefix: str,
    layer_path: str,
    clause_path: str,
) -> dict[str, Any]:
    profile = _profile()
    roles, targets = chapter_timing_targets(
        cast, layer, topic, fact_prefix=fact_prefix, clause_path=clause_path
    )
    labels = _input_labels(
        original, cast, layer, roles, fact_prefix=fact_prefix, layer_path=layer_path
    )
    rows = []
    for target in targets:
        node = target["node"]
        atom = profile["unit_branch_atoms"][node["trigram"]]
        matches = {
            unit: [
                {
                    "input_label_id": label["id"],
                    "branch": label["branch"],
                    "branch_fact_path": label["branch_fact_path"],
                    "source_value_kind": label.get("source_value_kind", "branch_label"),
                    "literal_named_unit_branch_atom_met": label["branch"]
                    in atom["unit_branches"][unit],
                    "full_source_timing_condition": None,
                    "real_outcome": None,
                }
                for label in labels[unit]
            ]
            for unit in UNITS
        }
        rows.append(
            {
                "selector_id": target["selector_id"],
                "source_rule": deepcopy(
                    profile["chapter_selectors"][target["selector_id"]]
                ),
                "role": node["role"],
                "trigram": node["trigram"],
                "relation_to_original_body": node["relation"],
                "trigram_fact_path": node["fact_path"] + ".name",
                "selected_source_context_condition": target[
                    "selected_source_context_condition"
                ],
                "condition_fact_path": target["condition_fact_path"],
                "full_source_context_authenticated": False,
                "literal_unit_branch_atom": deepcopy(atom),
                "input_unit_matches": matches,
                "label_disagreement_changes_literal_match": {
                    unit: len(
                        {r["literal_named_unit_branch_atom_met"] for r in matches[unit]}
                    )
                    > 1
                    for unit in UNITS
                },
                "unknown_units": [unit for unit in UNITS if not labels[unit]],
                "combined_units_membership": None,
                "full_source_timing_condition": None,
                "event_time": None,
            }
        )
    details = []
    for row in rows:
        pieces = []
        for unit in UNITS:
            values = row["input_unit_matches"][unit]
            pieces.append(
                UNIT_NAMES[unit]
                + (
                    "、".join(
                        r["input_label_id"]
                        + r["branch"]
                        + (
                            "相符"
                            if r["literal_named_unit_branch_atom_met"]
                            else "不符"
                        )
                        for r in values
                    )
                    if values
                    else "未采集"
                )
            )
        condition = (
            "条件满足"
            if row["selected_source_context_condition"] is True
            else (
                "前提不成立"
                if row["selected_source_context_condition"] is False
                else "前提未知"
            )
        )
        details.append(
            LABELS[row["role"]]
            + row["trigram"]
            + "（"
            + "；".join(pieces)
            + "；"
            + condition
            + "）"
        )
    summary = (
        "章句卦气年月日时分列："
        + ("；".join(details) if details else "所列范围未见章句指定的目标角色")
        + "。各单位仅核明列支标签；节月与名义农历月序标签分别保留，换日备选不改原年支，不选相符者作预测。数字、季节、五行及完整应期仍未裁定；不合并成日期、时限或现实结果。"
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": qi_branch_unit_ruleset(),
        "topic": topic,
        "input_unit_labels": labels,
        "input_unit_status": {
            unit: "labels_available_separate_bases" if labels[unit] else "not_collected"
            for unit in UNITS
        },
        "input_label_branch_disagreement": {
            unit: len({r["branch"] for r in labels[unit]}) > 1 for unit in UNITS
        },
        "source_selected_role_references": rows,
        "source_timing_month_basis_uniquely_adjudicated": False,
        "input_year_recast_from_day_alternative": False,
        "unit_matches_combined_or_voted": False,
        "literal_branch_membership_is_element_strength": False,
        "nonmembership_negates_full_source_condition": False,
        "numeric_stem_element_season_and_full_source_synthesis": "not_adjudicated",
        "candidate_event_dates": None,
        "event_time": None,
        "real_outcome": None,
        "real_world_observation_window": None,
        "independent_verified_observations": 0,
        "summary": summary,
    }


def apply_qi_branch_timing_references(
    cast: dict[str, Any], interpretation: dict[str, Any]
) -> None:
    topic = interpretation["interpretation_topic"]
    if topic not in {"wealth", "reputation"}:
        return
    main = _reading(
        cast,
        cast,
        interpretation,
        topic,
        fact_prefix="meihua",
        layer_path="interpretation",
        clause_path="interpretation.topic_reading",
    )
    interpretation["topic_reading"]["qi_branch_timing_reference"] = main
    interpretation["traditional_judgement"] += main["summary"]
    suffix = main["summary"]
    for i, row in enumerate(interpretation.get("casting_readings") or []):
        child = _reading(
            cast,
            cast["counting_variants"][i],
            row,
            topic,
            fact_prefix=f"meihua.counting_variants.{i}",
            layer_path=f"interpretation.casting_readings.{i}",
            clause_path=f"interpretation.casting_readings.{i}.topic_clause",
        )
        row["topic_clause"]["qi_branch_timing_reference"] = child
        row["traditional_judgement"] += child["summary"]
        suffix += (
            ("原数" if row["line_sum_basis"] == "raw_counts" else "卦序数")
            + "候选卦气年月日时分列："
            + child["summary"]
        )
    interpretation["comprehensive_judgement"] += suffix
