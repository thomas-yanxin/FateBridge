"""Consolidated Sukuyo cached source loaders, compact textual evidence, and compatibility helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Sequence

SU27_ORDER = "角亢氐房心尾箕斗女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸"
ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")
_SU27_SET = frozenset(SU27_ORDER)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SPECIAL_DAYS_SOURCE = _DATA_DIR / "sukuyo_t1299_special_days.json"
CALENDAR_DAY_SOURCE = _DATA_DIR / "sukuyo_t1299_days.json"
PADA_SOURCE = _DATA_DIR / "sukuyo_t1299_palace_padas.json"
SIX_PALACES_SOURCE = _DATA_DIR / "sukuyo_t1299_six_palaces.json"
TAIBAI_SOURCE = _DATA_DIR / "sukuyo_t1299_taibai.json"
CLOTHING_SOURCE = _DATA_DIR / "sukuyo_t1299_clothing.json"
TRAVEL_SOURCE = _DATA_DIR / "sukuyo_t1299_travel_directions.json"
LOWER_MANSIONS_SOURCE = _DATA_DIR / "sukuyo_t1299_lower_mansions.json"
LOWER_METHODS_SOURCE = _DATA_DIR / "sukuyo_t1299_lower_methods.json"
ACTIVITIES_SOURCE = _DATA_DIR / "sukuyo_t1299_activities.json"
SANJIU_DAYS_SOURCE = _DATA_DIR / "sukuyo_t1299_sanjiu_days.json"
GENERAL_DAYS_SOURCE = _DATA_DIR / "sukuyo_general_day_lists.json"

ACTIVITIES = (
    "social",
    "marriage",
    "travel",
    "relocation",
    "commerce",
    "study",
    "clothing",
)
SukuyoActivityDetail = Literal[
    "tailoring_garments",
    "making_garments",
    "repairing_garments",
    "wearing_garments",
    "wearing_new_garments",
    "royal_wearer",
    "sale",
    "borrowing",
    "lending",
    "long_distance_journey",
    "journey_abroad",
    "personal_departure",
    "private_journey",
    "royal_or_official_traveler",
    "long_distance_traveler_entering_residence",
    "southbound_journey",
    "northbound_journey",
    "eastbound_journey",
    "westbound_journey",
    "skill_learning",
    "earning_money",
    "sale_lactating_livestock",
    "sale_livestock",
    "spending_property",
    "receiving_property",
    "returning_property",
    "wealth_competition",
    "founding_school",
    "beginning_study",
    "learning_with_teacher",
    "purchase",
    "business_operation",
    "collecting_debt",
    "repaying_debt",
    "religious_learning",
    "monastic_dharma_request",
    "teaching_classics",
    "riding_training",
    "water_journey",
    "diplomatic_mission",
    "purchase_precious_goods",
    "purchase_livestock",
    "land_purchase",
    "land_sale",
    "social_gathering",
    "forming_friendship",
    "classical_text_study",
    "debate_learning",
]
DETAIL_TOPICS = {
    **dict.fromkeys(
        [
            "tailoring_garments",
            "making_garments",
            "repairing_garments",
            "wearing_garments",
            "wearing_new_garments",
            "royal_wearer",
        ],
        "clothing",
    ),
    **dict.fromkeys(
        [
            "sale",
            "borrowing",
            "lending",
            "earning_money",
            "sale_lactating_livestock",
            "sale_livestock",
            "spending_property",
            "receiving_property",
            "returning_property",
            "wealth_competition",
            "purchase",
            "business_operation",
            "collecting_debt",
            "repaying_debt",
            "purchase_precious_goods",
            "purchase_livestock",
            "land_purchase",
            "land_sale",
        ],
        "commerce",
    ),
    **dict.fromkeys(
        [
            "long_distance_journey",
            "journey_abroad",
            "personal_departure",
            "private_journey",
            "royal_or_official_traveler",
            "long_distance_traveler_entering_residence",
            "southbound_journey",
            "northbound_journey",
            "eastbound_journey",
            "westbound_journey",
            "water_journey",
            "diplomatic_mission",
        ],
        "travel",
    ),
    "skill_learning": "study",
    "founding_school": "study",
    "beginning_study": "study",
    "learning_with_teacher": "study",
    "religious_learning": "study",
    "monastic_dharma_request": "study",
    "teaching_classics": "study",
    "riding_training": "study",
    "social_gathering": "social",
    "forming_friendship": "social",
    "classical_text_study": "study",
    "debate_learning": "study",
}
DETAIL_PARENTS = {
    "tailoring_garments": ("making_garments",),
    "wearing_new_garments": ("wearing_garments",),
    "purchase_precious_goods": ("purchase",),
    "purchase_livestock": ("purchase",),
    "land_purchase": ("purchase",),
    "land_sale": ("sale",),
    "sale_lactating_livestock": ("sale_livestock",),
    "sale_livestock": ("sale",),
    "riding_training": ("skill_learning",),
    "monastic_dharma_request": ("religious_learning",),
}


def activity_detail_closure(details: Sequence[str]) -> tuple[list[str], list[dict]]:
    effective = list(dict.fromkeys(details))
    inferences = []
    for child in effective:
        for parent in DETAIL_PARENTS.get(child, ()):
            if parent not in effective:
                effective.append(parent)
                inferences.append({"from_detail": child, "implied_detail": parent})
    return effective, inferences


def validate_activity_details(activity: str | None, details: Sequence[str]) -> None:
    if isinstance(details, (str, bytes)):
        raise ValueError("activity_details必须为明确条件的列表")
    for detail in details:
        if not isinstance(detail, str) or detail not in DETAIL_TOPICS:
            raise ValueError("未知的宿占事项细节")
        if activity != DETAIL_TOPICS[detail]:
            raise ValueError(f"事项细节{detail}只适用于{DETAIL_TOPICS[detail]}")


@lru_cache(maxsize=64)
def load_source(path: Path | str) -> Any:
    """Load and cache JSON source once without per-call deepcopy."""
    return json.loads(Path(path).read_bytes())


def _normalize_su27(name: str) -> str:
    norm = name.strip().removesuffix("宿").translate(ALIASES)
    if norm not in _SU27_SET:
        raise ValueError(f"宿曜二十七宿不包含：{name}")
    return norm


def with_text_layers(rule: dict[str, Any]) -> dict[str, Any]:
    """Return compact rule representation preserving id, layer, and assessment."""
    out: dict[str, Any] = {}
    for key in (
        "rule_id",
        "layer",
        "selectors",
        "activities",
        "assessment",
        "meaning",
        "locator",
        "source_excerpt",
        "volume",
        "applicability",
        "topic_condition",
        "activity_conditions",
        "direction",
    ):
        if key in rule:
            out[key] = rule[key]
    return out


@lru_cache(maxsize=1)
def _special_day_index() -> dict[tuple[str, int], list[dict[str, Any]]]:
    bundle = load_source(SPECIAL_DAYS_SOURCE)
    idx: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for witness in bundle["witnesses"]:
        wid = witness["id"]
        for row in witness["rows"]:
            idx.setdefault((wid, row["weekday_index"]), []).append(row)
    return idx


def special_day_evidence(
    mansion: str | None,
    weekday: int,
    candidates: Sequence[str] = (),
    *,
    weekday_basis: str = "modern_utc_plus08_civil_midnight",
) -> dict[str, Any]:
    """Return slim special-day witness matches (甘露/金刚峰/罗刹), without editorial walls."""
    del candidates, weekday_basis
    bundle = load_source(SPECIAL_DAYS_SOURCE)
    idx = _special_day_index()
    upper_rows = idx.get(("upper_taisho", weekday), [])
    lower_rows = idx.get(("lower_taisho", weekday), [])

    def _compact_row(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "label": r["label"],
            "luminary": r["luminary"],
            "mansion": r["mansion"],
            "locator": r["locator"],
        }

    upper_matched = (
        [_compact_row(r) for r in upper_rows if r["mansion"] == mansion]
        if mansion
        else []
    )
    lower_matched = (
        [_compact_row(r) for r in lower_rows if r["mansion"] == mansion]
        if mansion
        else []
    )
    upper_labels = list(dict.fromkeys(r["label"] for r in upper_matched))
    lower_labels = list(dict.fromkeys(r["label"] for r in lower_matched))
    return {
        "ruleset_id": bundle["id"],
        "selected_primary": "upper_taisho",
        "primary": {
            "matched_labels": upper_labels,
            "matched_rows": upper_matched,
        },
        "comparisons": [
            {
                "witness": "upper_taisho",
                "matched_labels": upper_labels,
                "matched_rows": upper_matched,
            },
            {
                "witness": "lower_taisho",
                "matched_labels": lower_labels,
                "matched_rows": lower_matched,
                "unresolved_rows": [
                    {
                        "label": r["label"],
                        "literal_mansion": r["literal_mansion"],
                    }
                    for r in lower_rows
                    if r.get("reading_status") != "recognized_mansion"
                ],
            },
        ],
        "ganro_date": "甘露" in upper_labels,
        "kongoubu_date": "金刚峰" in upper_labels,
        "rasetsu_date": "罗刹" in upper_labels,
    }


def calendar_day_evidence(
    lunar_day: int, *, host_calendar_label: str = "中国农历"
) -> dict[str, Any]:
    """Return slim T1299 lunar day classification (no 96 KB clock doctrine)."""
    del host_calendar_label
    if type(lunar_day) is not int or not 1 <= lunar_day <= 30:
        raise ValueError("黑白月入月日须为1至30的整数")
    named = load_source(CALENDAR_DAY_SOURCE)["named_days"][(lunar_day - 1) % 15]
    general = load_source(GENERAL_DAYS_SOURCE)
    classifications = []
    for w in general["witnesses"]:
        assessment = (
            "favorable"
            if lunar_day in w["favorable_lunar_days"]
            else ("caution" if lunar_day in w["conditional_lunar_days"] else None)
        )
        if assessment is not None:
            classifications.append(
                {
                    "witness": w["witness"],
                    "assessment": assessment,
                    "locator": w["classification_locator"],
                }
            )
    return {
        "lunar_day": lunar_day,
        "lunar_half": "白" if lunar_day <= 15 else "黑",
        "half_day": (lunar_day - 1) % 15 + 1,
        "upper_name": named.get("upper_name"),
        "lower_name": named.get("lower_name"),
        "classifications": classifications,
    }


@lru_cache(maxsize=1)
def _pada_cells() -> tuple[dict[str, Any], ...]:
    palaces = load_source(PADA_SOURCE)["palaces"]
    counts: dict[str, int] = {}
    cells: list[dict[str, Any]] = []
    for palace in palaces:
        for segment in palace["segments"]:
            name, amount = segment["mansion"], segment["count"]
            counts.setdefault(name, 0)
            for _ in range(amount):
                counts[name] += 1
                cells.append(
                    {
                        "mansion": name,
                        "pada": counts[name],
                        "palace_ordinal": palace["ordinal"],
                        "palace_name": palace["name"],
                        "ruler_luminary": palace["ruler_luminary"],
                        "locator": palace["locator"],
                    }
                )
    return tuple(cells)


def validate_textual_pada(pada: int | None) -> None:
    if pada is not None and (type(pada) is not int or not 1 <= pada <= 4):
        raise ValueError("textual_pada仅为原典查表的1..4整数足序；不猜测实际出生足位")


def palace_reference(
    context: dict[str, Any], textual_pada: int | None = None
) -> dict[str, Any]:
    """Return slimmed 27x4 palace pada reference."""
    validate_textual_pada(textual_pada)
    bundle = load_source(PADA_SOURCE)
    primary = context.get("natal_su27")
    names = (
        [primary]
        if primary
        else list(dict.fromkeys(context.get("candidate_su27s", [])))
    )
    complete = (
        primary is not None
        or bool(names)
        and context.get("profile_calculation", {}).get(
            "candidate_set_complete_under_declared_reconstructions"
        )
        is True
    )
    cells = _pada_cells()
    rows = [
        dict(cell)
        for name in names
        for p in ([textual_pada] if textual_pada is not None else range(1, 5))
        for cell in cells
        if cell["mansion"] == _normalize_su27(name) and cell["pada"] == p
    ]
    ordinals = list(dict.fromkeys(r["palace_ordinal"] for r in rows))
    palaces = [
        {k: v for k, v in p.items() if k not in ("segments", "textual_variants")}
        for p in bundle["palaces"]
        if p["ordinal"] in ordinals
    ]
    resolved = complete and len(palaces) == 1
    return {
        "ruleset_id": bundle["id"],
        "status": (
            "candidate_set_incomplete"
            if not complete
            else (
                "palace_resolved_from_complete_candidates"
                if resolved and primary is None
                else (
                    "palace_resolved_pada_unspecified"
                    if resolved and textual_pada is None
                    else (
                        "reference_cell_selected"
                        if resolved
                        else "mansion_or_pada_ambiguous"
                    )
                )
            )
        ),
        "mansion": primary,
        "mansion_candidates": names,
        "textual_pada": textual_pada,
        "selected_palace": palaces[0] if resolved else None,
        "candidate_palaces": palaces,
        "rows": rows,
    }


def six_palace_reference(natal_mansion: str | None) -> dict[str, Any]:
    source = load_source(SIX_PALACES_SOURCE)
    order = source["mansion_order"]
    if natal_mansion is not None:
        natal_mansion = _normalize_su27(natal_mansion)
    start = order.index(natal_mansion) if natal_mansion is not None else None
    return {
        "ruleset_id": source["id"],
        "status": "natal_reference" if start is not None else "natal_mansion_required",
        "natal_mansion": natal_mansion,
        "members": (
            [
                {
                    "name": row["name"],
                    "inclusive_ordinal": row["inclusive_ordinal"],
                    "mansion": order[(start + row["inclusive_ordinal"] - 1) % 27],
                }
                for row in source["positions"]
            ]
            if start is not None
            else []
        ),
    }


def taibai_direction_reference(lunar_day: int) -> dict[str, Any]:
    if type(lunar_day) is not int or not 1 <= lunar_day <= 30:
        raise ValueError("太白月日方位表只接受实际入月日1至30")
    source = load_source(TAIBAI_SOURCE)
    row = next(r for r in source["rows"] if lunar_day in r["lunar_days"])
    return {
        "ruleset_id": source["id"],
        "lunar_day": lunar_day,
        "location": row["literal_location"],
        "horizontal_direction": row["horizontal_direction"],
        "realm": row["realm"],
        "row_id": row["row_id"],
    }


def clothing_reference(calendar: dict[str, Any]) -> dict[str, Any]:
    source = load_source(CLOTHING_SOURCE)
    mansion = calendar.get("natal_su27")
    candidates = [mansion] if mansion else calendar.get("candidate_su27s", [])
    rows = []
    for value in candidates:
        name = _normalize_su27(value)
        match = next(r for r in source["verse_rows"] if r["mansion"] == name)
        primary = (
            "favorable" if name in source["primary_positive_mansions"] else "caution"
        )
        rows.append(
            {
                "mansion": name,
                "verse": match,
                "primary_assessment": primary,
            }
        )
    assessments = {r["primary_assessment"] for r in rows}
    return {
        "ruleset_id": source["id"],
        "rows": rows,
        "primary_assessment": (
            next(iter(assessments)) if len(assessments) == 1 else None
        ),
    }


def travel_direction_evidence(
    mansion: str | None, candidates: Sequence[str] = ()
) -> dict[str, Any]:
    del candidates
    bundle = load_source(TRAVEL_SOURCE)
    records = (
        [with_text_layers(r) for r in bundle["rules"] if mansion in r["selectors"]]
        if mansion
        else []
    )
    return {
        "ruleset_id": bundle["id"],
        "status": "named_day_reference" if mansion else "candidate_only",
        "mansion": mansion,
        "selected_records": records,
    }


def lower_mansion_evidence(mansion: str | None) -> dict[str, Any]:
    bundle = load_source(LOWER_MANSIONS_SOURCE)
    record = next((r for r in bundle["records"] if r["mansion"] == mansion), None)
    if mansion is not None and record is None:
        raise ValueError("下卷逐宿证据只支持27宿（不含牛）")
    return {
        "status": "source_record_available" if record else "not_evaluated",
        "mansion": mansion,
        "ruleset_id": bundle["id"],
        "locator": record["locator"] if record else None,
    }


def lower_methods_evidence(
    mansion: str | None,
    luminary: str,
    upper_nature: str | None,
    *,
    weekday_basis: str = "modern_utc_plus08_civil_midnight",
) -> dict[str, Any]:
    bundle = load_source(LOWER_METHODS_SOURCE)
    if mansion == "牛":
        raise ValueError("下卷宿性证言不能把牛宿代入历日27宿")
    group = next(
        (g for g in bundle["nature_groups"] if mansion and mansion in g["members"]),
        None,
    )
    weekday = next(
        (w for w in bundle["weekday_records"] if w["luminary"] == luminary), None
    )
    if weekday is None:
        raise ValueError("七曜只支持日月火水木金土")
    normalized_upper = "轻" if upper_nature == "轻燥" else upper_nature
    return {
        "ruleset_id": bundle["id"],
        "nature": {
            "status": "enumerated_membership_reference" if group else "not_evaluated",
            "mansion": mansion,
            "selected_group": (
                {"name": group["name"], "members": group["members"]} if group else None
            ),
            "upper_nature": upper_nature,
            "membership_differs_from_upper": (
                group["name"] != normalized_upper if group else None
            ),
        },
        "weekday": {
            "luminary": weekday["luminary"],
            "basis": weekday_basis,
        },
    }


def conjunction_doctrine(
    mansion: str | None, candidates: Sequence[str] = ()
) -> dict[str, Any]:
    del candidates
    bundle = load_source(LOWER_MANSIONS_SOURCE)
    doctrine = bundle["conjunction_doctrine"]
    group = (
        next((g for g in doctrine["groups"] if mansion in g["members"]), None)
        if mansion
        else None
    )
    return {
        "ruleset_id": doctrine["id"],
        "status": "classified_name_reference" if mansion else "candidate_only",
        "mansion": mansion,
        "selected_group": dict(group) if group else None,
    }


def assess_activity(
    day: dict[str, Any],
    activity: str | None,
    activity_details: Sequence[str] | None = None,
) -> dict[str, Any] | None:
    if activity is None:
        return None
    if activity not in ACTIVITIES:
        raise ValueError(
            "activity仅支持social/marriage/travel/relocation/commerce/study/clothing"
        )

    validate_activity_details(activity, activity_details or [])
    details = list(dict.fromkeys(activity_details or []))
    effective_details, detail_inferences = activity_detail_closure(details)
    relative = (day.get("personal_day") or {}).get("relation")
    mansion = day.get("day_mansion")
    selectors: dict[str, Sequence[Any]] = {
        "sanjiu": [relative["relation"]] if relative else [],
        "nature": [day["nature"]] if day.get("nature") else [],
        "weekday": [day["weekday"]["luminary"]],
        "special_day": day["special_day_labels"],
        "named_day": [day["calendar_day"]["lunar_day"]],
        "lower_mansion": [mansion] if mansion else [],
        "lower_nature": (
            [day["lower_methods"]["nature"]["selected_group"]["name"]]
            if (day.get("lower_methods") or {}).get("nature", {}).get("selected_group")
            else []
        ),
        "lower_weekday": [day["weekday"]["luminary"]],
        "travel_direction": [mansion] if mansion else [],
        "lower_special_day": day["special_day_evidence"]["comparisons"][1][
            "matched_labels"
        ],
    }
    if activity == "clothing" and day.get("clothing_reference"):
        ref = day["clothing_reference"]
        selectors["clothing_chapter"] = (
            [ref["primary_assessment"]] if ref.get("primary_assessment") else []
        )
        selectors["clothing_upper_mansion"] = [mansion] if mansion else []

    rule_sources = [
        *load_source(ACTIVITIES_SOURCE)["rules"],
        *load_source(CALENDAR_DAY_SOURCE)["activity_rules"],
        *load_source(LOWER_MANSIONS_SOURCE)["rules"],
        *load_source(LOWER_METHODS_SOURCE)["rules"],
        *load_source(TRAVEL_SOURCE)["rules"],
        *load_source(SPECIAL_DAYS_SOURCE)["activity_rules"],
        *load_source(SANJIU_DAYS_SOURCE)["activity_rules"],
        *(load_source(CLOTHING_SOURCE)["rules"] if activity == "clothing" else []),
    ]
    matches: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
    for raw_rule in rule_sources:
        if activity not in raw_rule["activities"]:
            continue
        if not set(raw_rule["selectors"]).intersection(
            selectors.get(raw_rule["layer"], ())
        ):
            continue
        rule = with_text_layers(raw_rule)
        condition = raw_rule.get("activity_conditions", {}).get(activity)
        if condition:
            any_of = condition.get("any_of", [])
            all_of = condition.get("all_of", [])
            matched_details = [d for d in effective_details if d in [*any_of, *all_of]]
            applies = (
                bool(any_of or all_of)
                and (not any_of or bool(set(effective_details).intersection(any_of)))
                and all(d in effective_details for d in all_of)
            )
            entry = {
                **rule,
                "applicability": "activity_detail_required",
                "matched_activity_details": matched_details,
                "applied_to_aggregate": applies,
            }
            (matches if applies else conditional).append(entry)
        else:
            matches.append(rule)
    return {
        "activity": activity,
        "activity_details": details,
        "effective_activity_details": effective_details,
        "detail_inferences": detail_inferences,
        "matched_rules": matches,
        "conditional_rules": conditional,
    }


def candidate_compatibility_reading(*args: Any, **kwargs: Any) -> str:
    """Compatibility helper for untouched services/divination.py; prose walls omitted."""
    del args, kwargs
    return ""


def joint_reconstruction_contract(analysis: dict[str, Any]) -> str:
    """Describe the join actually returned, including states with no row filter."""
    shared = analysis.get("shared_reconstruction_analysis")
    if not shared:
        return ""
    status = shared.get("status")
    resolved = analysis.get("status") == "not_needed"
    if status == "applied":
        scope = (
            "共同重建状态applied：rows仅列双方共同采用同一套具名现代重建时有完整联合支持的条件组合；"
            "完整原无约束矩阵保留在unconstrained_rows。"
        )
    elif status == "not_shared":
        scope = "共同重建状态not_shared：档案、算法、来源或宿主历法身份未核成相同，未施加共同重建约束。" + (
            "宿名已定，rows为空，有向关系由person1_to_person2和person2_to_person1交付。"
            if resolved
            else "rows仍为原无约束外包络，不能视为通过共同模型筛选。"
        )
    elif status == "incomplete":
        scope = "共同重建状态incomplete：支持覆盖不完整，未筛掉任何原候选行，缺支持记录不能判成不成立。"
        if resolved:
            scope += (
                "宿名已定，rows为空，有向关系由person1_to_person2和person2_to_person1交付；"
                "已返回的具体模型条件另见resolved_support，不据此确定唯一模型。"
            )
        else:
            scope += "rows仍为原无约束外包络。"
            if "unconstrained_rows" in analysis:
                scope += "完整原矩阵也保留在unconstrained_rows。"
    elif status == "not_needed":
        scope = (
            "共同重建状态not_needed：双方宿名已定，rows为空；有向关系由person1_to_person2和person2_to_person1交付。"
            "resolved_support保留具体模型、日期与半日条件，不能由宿名一致确定唯一模型或半日。"
        )
    else:
        scope = "共同重建状态未识别，不能断言已筛选rows、支持覆盖完整或原矩阵另存。"
    return scope + (
        "未知日期、半日各自保留，不拆散完整联合支持记录再交叉；"
        "未获共同支持不等于历史绝对不可能，未裁定原典优先次序。"
    )


def compatibility_reference_notes(*args: Any, **kwargs: Any) -> str:
    del args, kwargs
    return ""


def research_scope(*args: Any, **kwargs: Any) -> dict[str, Any]:
    del args, kwargs
    return {"unknown_direction_rows": []}


def scope_lines(*args: Any, **kwargs: Any) -> list[str]:
    del args, kwargs
    return [""]
