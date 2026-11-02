"""Source-scoped Mei Hua evidence derived from the actual cast, without scores.

Calendar conventions are explicit software choices. Relationships keep the
original static body throughout the initial, mutual and changed stages.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.hexagram_relations import relationship_by_role

_TENDENCIES = {
    "体用比和": ("比和", "体用同气，传统取协调之意"),
    "体生用": ("耗泄", "体生外卦，传统提示主体有所耗泄，不能据此承诺日后回报"),
    "体克用": ("制用", "体制外卦，传统取可以制用之意，仍须结合体气与互变"),
    "用生体": ("生助", "外卦生体，传统取有扶助之意"),
    "用克体": ("受克", "外卦克体，传统提示存在制约"),
}


@lru_cache(maxsize=1)
def _ruleset() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data/meihua/time-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def meihua_ruleset() -> dict[str, Any]:
    """Return an isolated copy; callers cannot mutate the cached source profile."""
    return deepcopy(_ruleset())


def _season(branch: str) -> tuple[str, str, str]:
    if branch not in set("子丑寅卯辰巳午未申酉戌亥"):
        raise ValueError("季令月支必须为十二地支之一。")
    if branch in {"辰", "戌", "丑", "未"}:
        return "四季土月", "土", "水"
    for branches, season, strong, weak in (
        ("寅卯", "春", "木", "土"),
        ("巳午", "夏", "火", "金"),
        ("申酉", "秋", "金", "木"),
        ("亥子", "冬", "水", "火"),
    ):
        if branch in branches:
            return season, strong, weak
    raise ValueError("季令月支必须为十二地支之一。")


def meihua_stage_relations(
    meihua: dict[str, Any], *, fact_prefix: str = "meihua"
) -> list[dict[str, Any]]:
    """One relation engine for selected casts and every retained count variant."""
    changed = meihua["changed_hexagram"]
    mutual = meihua["mutual_hexagram"]
    body, use = meihua["body_trigram"], meihua["use_trigram"]
    body_position = "upper" if meihua["moving_palace"] == "下卦" else "lower"
    use_position = "lower" if body_position == "upper" else "upper"
    stages = []
    for role, stage, trigram, path in (
        ("use", "initial", use, "meihua.use_trigram"),
        (
            "body_mutual",
            "middle",
            mutual[body_position],
            f"meihua.mutual_hexagram.{body_position}",
        ),
        (
            "use_mutual",
            "middle",
            mutual[use_position],
            f"meihua.mutual_hexagram.{use_position}",
        ),
        (
            "changed_use",
            "final",
            changed[use_position],
            f"meihua.changed_hexagram.{use_position}",
        ),
    ):
        relation = relationship_by_role(body["element"], trigram["element"])
        tendency, meaning = _TENDENCIES[relation]
        stages.append(
            {
                "role": role,
                "stage": stage,
                "body": body["name"],
                "body_element": body["element"],
                "trigram": trigram["name"],
                "element": trigram["element"],
                "relation": relation,
                "traditional_tendency": tendency,
                "meaning": meaning,
                "fact_path": fact_prefix + path.removeprefix("meihua"),
                "rule_id": "stages" if stage != "middle" else "mutual_roles",
            }
        )
    return stages


def meihua_seasonal_strength(
    meihua: dict[str, Any],
    month_branch: str | None,
    *,
    fact_prefix: str = "meihua",
) -> dict[str, Any] | None:
    """Apply the same declared month to each cast's own body and mutuals."""
    if month_branch is None:
        return None
    season, strong, weak = _season(month_branch)
    body = meihua["body_trigram"]
    roles = [
        ("body", body["name"], body["element"], fact_prefix + ".body_trigram"),
        *[
            (row["role"], row["trigram"], row["element"], row["fact_path"])
            for row in meihua_stage_relations(meihua, fact_prefix=fact_prefix)
        ],
    ]
    return {
        "month_branch": month_branch,
        "season": season,
        "basis": "solar_term_month_earth_month_priority",
        "rule_id": "season",
        "convention_rule_id": "season_policy",
        "trigrams": [
            {
                "role": role,
                "trigram": trigram,
                "element": element,
                "strength": (
                    "旺"
                    if element == strong
                    else "衰" if element == weak else "原文未定"
                ),
                "fact_path": path,
            }
            for role, trigram, element, path in roles
        ],
    }


def meihua_traditional_readings(
    stages: list[dict[str, Any]],
    seasonal: dict[str, Any] | None,
    *,
    internal_countercontrol: dict[str, Any] | None = None,
    seasonal_qualification: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Render only the supplied, already computed cast facts."""
    labels = {
        "use": "初应之用",
        "body_mutual": "中间之体互",
        "use_mutual": "中间之用互",
        "changed_use": "终应之变用",
    }
    readings = [
        {
            "role": row["role"],
            "fact_path": row["fact_path"],
            "relation": row["relation"],
            "text": f"{labels[row['role']]}{row['trigram']}对原体{row['body']}为{row['relation']}，{row['meaning']}。",
        }
        for row in stages
    ]
    text = "".join(row["text"] for row in readings)
    if stages:
        if internal_countercontrol is None:
            from .meihua_countercontrol import build_internal_countercontrol

            internal_countercontrol = build_internal_countercontrol(stages)
        text += internal_countercontrol["summary"]
    if seasonal:
        body = next(row for row in seasonal["trigrams"] if row["role"] == "body")
        text += (
            f"按已声明的节月约定，{seasonal['month_branch']}月取{seasonal['season']}，"
            f"体卦{body['trigram']}的季令标记为{body['strength']}。"
        )
    if stages:
        if seasonal_qualification is None:
            from .meihua_seasonal_reading import build_seasonal_qualification

            assert internal_countercontrol is not None
            seasonal_qualification = build_seasonal_qualification(
                stages, seasonal, internal_countercontrol
            )
        text += seasonal_qualification["summary"]
    return readings, text


def build_meihua_evidence(
    meihua: dict[str, Any],
    *,
    lunar_year: int | None,
    is_leap_month: bool,
    timezone_name: str | None,
    month_branch: str | None,
    casting_trace: list[dict[str, Any]] | None = None,
    selected_ruleset: dict[str, Any] | None = None,
    calendar_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enrich one cast with traceable rules; do not recast or infer events."""
    seed = meihua["seed"]
    base = meihua["base_hexagram"]
    changed = meihua["changed_hexagram"]
    mutual = meihua["mutual_hexagram"]
    body, use = meihua["body_trigram"], meihua["use_trigram"]
    stages = meihua_stage_relations(meihua)

    if casting_trace is None:
        year_number = "子丑寅卯辰巳午未申酉戌亥".index(seed["year_branch"]) + 1
        hour_number = "子丑寅卯辰巳午未申酉戌亥".index(seed["hour_branch"]) + 1
        upper_sum = year_number + seed["lunar_month"] + seed["lunar_day"]
        total_sum = upper_sum + hour_number
    pure = base["binary_code"] in {"111111", "000000"}
    mutual_source = changed if pure else base
    trace = (
        deepcopy(casting_trace)
        if casting_trace is not None
        else [
            {
                "rule_id": "time_seed",
                "operation": "year_branch_number + lunar_month + lunar_day",
                "inputs": {
                    "year_number": year_number,
                    "month": seed["lunar_month"],
                    "day": seed["lunar_day"],
                },
                "result": upper_sum,
            },
            {
                "rule_id": "time_seed",
                "operation": "upper_sum + hour_branch_number",
                "inputs": {"upper_sum": upper_sum, "hour_number": hour_number},
                "result": total_sum,
            },
            {
                "rule_id": "remainders",
                "operation": "upper_sum % 8 or 8; total_sum % 8 or 8; total_sum % 6 or 6",
                "inputs": {"upper_sum": upper_sum, "total_sum": total_sum},
                "result": {
                    "upper_number": seed["upper_number"],
                    "lower_number": seed["lower_number"],
                    "moving_line": seed["moving_line"],
                },
            },
        ]
    )
    trace.extend(
        [
            {
                "rule_id": "mutual",
                "operation": "lines[2,3,4] + lines[3,4,5], one-based bottom-to-top",
                "inputs": {
                    "basis": "changed_hexagram" if pure else "base_hexagram",
                    "binary_code": mutual_source["binary_code"],
                },
                "result": mutual["binary_code"],
            },
            {
                "rule_id": "body_use",
                "operation": "moving trigram = use; static trigram = body",
                "inputs": {"moving_line": seed["moving_line"]},
                "result": {"body": body["name"], "use": use["name"]},
            },
        ]
    )
    profile = (
        deepcopy(selected_ruleset) if selected_ruleset is not None else meihua_ruleset()
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": profile,
        "calendar_policy": (
            deepcopy(calendar_policy)
            if calendar_policy is not None
            else {
                "lunar_year": lunar_year,
                "year_boundary": "lunar_new_year",
                "day_boundary": "local_midnight",
                "is_leap_month": is_leap_month,
                "leap_month_rule": "repeat_nominal_month_number",
                "timezone": timezone_name,
                "date_basis": "selected_zone_civil_date",
                "hour_basis": "civil_double_hour",
                "true_solar_time_applied": False,
                "minute_role": "定位钟时；不另加分钟数。同一时辰且不跨民用午夜时取数相同。",
                "rule_kind": "software_convention",
            }
        ),
        "rule_trace": trace,
        "stage_relations": stages,
        "seasonal_strength": meihua_seasonal_strength(meihua, month_branch),
        "evidence_scope": {
            "classical_coverage": "partial",
            "implemented": [
                "time_seed",
                "remainders",
                "mutual",
                "body_use",
                "stages",
                "mutual_roles",
                "season",
            ],
            "not_implemented": [
                "other_casting_methods",
                "external_omens",
                "exact_event_timing",
                "all_topic_judgements",
            ],
            "interpretation_basis": "traditional_relations_with_separately_labeled_modern_advice",
            "real_world_efficacy": "not_tested",
            "authority_certified": False,
        },
    }
