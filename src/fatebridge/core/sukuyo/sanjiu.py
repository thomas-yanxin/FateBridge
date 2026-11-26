"""Consolidated Sanjiu (三九法), Ryohan inversion (凌犯期間), and Kuyou annual stars (九執當年星)."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Sequence

from fatebridge.core.sukuyo.texts import (
    ALIASES,
    SU27_ORDER,
    load_source,
)

SU28_NAMES = "角亢氐房心尾箕斗牛女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸"
_TRAD = str.maketrans("虚娄毕参张轸", "虛婁畢參張軫")
DistanceRule = Literal["symmetric", "cyclic", "none"]

RELATION_TEMPLATE = [
    "命",
    "栄",
    "衰",
    "安",
    "危",
    "成",
    "壊",
    "友",
    "親",
    "業",
    "栄",
    "衰",
    "安",
    "危",
    "成",
    "壊",
    "友",
    "親",
    "胎",
    "栄",
    "衰",
    "安",
    "危",
    "成",
    "壊",
    "友",
    "親",
]

RELATION_PAIR = {
    "命": "命",
    "業": "業胎",
    "胎": "業胎",
    "栄": "栄親",
    "親": "栄親",
    "友": "友衰",
    "衰": "友衰",
    "安": "安壊",
    "壊": "安壊",
    "危": "危成",
    "成": "危成",
}

RELATION_BRIEF = {
    "命": ("同宿共鸣", "吉"),
    "業": ("前世因缘", "吉"),
    "胎": ("未来承接", "吉"),
    "栄": ("繁荣滋养", "吉"),
    "親": ("亲厚护持", "吉"),
    "友": ("志趣相投", "吉"),
    "衰": ("消磨耗损", "凶"),
    "安": ("安定受助", "吉"),
    "壊": ("破耗受克", "凶"),
    "危": ("险阻试炼", "凶"),
    "成": ("成就助缘", "吉"),
}

LINGBI_SOURCE = (
    Path(__file__).resolve().parents[2] / "data/sukuyo_kenyu_selected_lingbi.json"
)

# 九執當年星 (九曜星): nominal age 1..9 cycle (余数1=羅睺 ... 9=木曜).
KUYOU_CYCLE: tuple[dict[str, Any], ...] = (
    {"ordinal": 1, "star": "羅睺星", "luminary": "羅睺", "fortune": "大凶"},
    {"ordinal": 2, "star": "土曜星", "luminary": "土", "fortune": "凶/半吉"},
    {"ordinal": 3, "star": "水曜星", "luminary": "水", "fortune": "吉"},
    {"ordinal": 4, "star": "金曜星", "luminary": "金", "fortune": "半吉"},
    {"ordinal": 5, "star": "日曜星", "luminary": "日", "fortune": "大吉"},
    {"ordinal": 6, "star": "火曜星", "luminary": "火", "fortune": "大凶"},
    {"ordinal": 7, "star": "計都星", "luminary": "計都", "fortune": "大凶"},
    {"ordinal": 8, "star": "月曜星", "luminary": "月", "fortune": "大吉/半吉"},
    {"ordinal": 9, "star": "木曜星", "luminary": "木", "fortune": "大吉"},
)

_MODELS = (
    "adjacent_month_short_day_assignment",
    "repeat_regular_month_first_day_assignment",
)
_JOINT_METHOD = "shared_hinoo_reconstruction_support_v1"


def normalize_mansion(name: str) -> str:
    """Normalize a classical 27-mansion name (rejecting 牛宿)."""
    if not name or not isinstance(name, str):
        raise ValueError("宿名不能为空")
    norm = name.strip().removesuffix("宿").translate(ALIASES)
    if norm == "牛":
        raise ValueError("牛宿不入宿曜二十七宿三九圈（四足分属女/斗）")
    if norm not in SU27_ORDER:
        raise ValueError(f"未知的二十七宿名称：{name}")
    return norm


def distance_band_for_offset(
    offset: int, *, distance_rule: DistanceRule = "symmetric"
) -> str | None:
    """Classify Sanjiu distance under 'symmetric' (d=min(off, 27-off)), 'cyclic', or 'none'."""
    if distance_rule not in ("symmetric", "cyclic", "none"):
        raise ValueError(
            f"distance_rule 仅支持 symmetric/cyclic/none，收到：{distance_rule}"
        )
    if distance_rule == "none" or offset in (0, 9, 18):
        return None
    if distance_rule == "symmetric":
        d = min(offset, 27 - offset)
        return "近距离" if d <= 4 else ("中距离" if d <= 8 else "远距离")
    return "近距离" if offset <= 8 else ("中距离" if offset <= 17 else "远距离")


def relation_between_su27(
    self_su27: str,
    other_su27: str,
    *,
    distance_rule: DistanceRule = "symmetric",
) -> dict[str, Any]:
    """Compute directional Sanjiu relationship between two 27-mansions."""
    s = normalize_mansion(self_su27)
    o = normalize_mansion(other_su27)
    idx_s = SU27_ORDER.index(s)
    idx_o = SU27_ORDER.index(o)
    offset = (idx_o - idx_s) % 27
    rel = RELATION_TEMPLATE[offset]
    pair = RELATION_PAIR[rel]
    dist = distance_band_for_offset(offset, distance_rule=distance_rule)
    meaning, assessment = RELATION_BRIEF[rel]
    return {
        "relation": rel,
        "pair": pair,
        "distance": dist,
        "distance_rule": distance_rule,
        "meaning": meaning,
        "self_su27": s,
        "other_su27": o,
        "offset": offset,
        "sequence_group": offset // 9 + 1,
        "traditional_assessment": assessment,
    }


def personal_day_evidence(
    natal_mansion: str | None,
    day_mansion: str | None,
    *,
    distance_rule: DistanceRule = "symmetric",
) -> dict[str, Any] | None:
    """Compute compact natal-to-day Sanjiu relation when both mansions are known."""
    if not natal_mansion or not day_mansion:
        return None
    rel = relation_between_su27(natal_mansion, day_mansion, distance_rule=distance_rule)
    return {"relation": rel}


def kuyou_for_age(nominal_age: int) -> dict[str, Any]:
    """Return the 九執當年星 (Kuyou annual star) for a nominal age >= 1."""
    if (
        isinstance(nominal_age, bool)
        or not isinstance(nominal_age, int)
        or nominal_age < 1
    ):
        raise ValueError("数え年（虚岁）须为大于等于1的整数")
    entry = KUYOU_CYCLE[(nominal_age - 1) % 9]
    return {"nominal_age": nominal_age, **entry}


def kuyou_annual_star(birth_year: int, target_year: int) -> dict[str, Any]:
    """Compute 九執當年星 from birth year and target year (nominal age = target - birth + 1)."""
    if target_year < birth_year:
        raise ValueError("目标流年不能早于出生年")
    age = target_year - birth_year + 1
    return {"birth_year": birth_year, "target_year": target_year, **kuyou_for_age(age)}


@lru_cache(maxsize=1)
def _ryohan_index() -> dict[tuple[int, str], tuple[int, int, str]]:
    data = load_source(LINGBI_SOURCE)
    return {
        (row["month"], row["month_start_luminary"]): (
            row["start_day"],
            row["end_day"],
            row["literal"],
        )
        for row in data["printed_rows"]
    }


def assess_ryohan(
    lunar_month: int,
    lunar_day: int,
    month_start_luminary: str,
    *,
    relation: str | None = None,
    special_labels: Sequence[str] = (),
    urgent: bool = False,
) -> dict[str, Any]:
    """Check Kenyu Lingbi Ryohan (凌犯期間) and invert Sanjiu + 甘露/金刚峰/罗刹 assessments."""
    window = _ryohan_index().get((lunar_month, month_start_luminary))
    in_ryohan = bool(window and window[0] <= lunar_day <= window[1])
    relation_inverted = False
    effective_assessment: str | None = (
        RELATION_BRIEF[relation][1] if relation in RELATION_BRIEF else None
    )
    if in_ryohan and relation is not None:
        if relation in ("衰", "危", "壊"):
            relation_inverted = True
            effective_assessment = (
                "急事可用（反吉）" if urgent else "吉凶翻转（衰危壊反可用）"
            )
        elif relation in ("栄", "成", "友", "親", "安", "命", "胎", "業"):
            relation_inverted = True
            effective_assessment = "不可取用（反凶）"

    normalized_specials = [s for s in special_labels]
    inverted_specials = (
        [s for s in normalized_specials if s in ("甘露", "金刚峰", "金剛峯")]
        if in_ryohan
        else []
    )
    return {
        "in_ryohan": in_ryohan,
        "lunar_month": lunar_month,
        "lunar_day": lunar_day,
        "month_start_luminary": month_start_luminary,
        "matched_window": (
            {"start_day": window[0], "end_day": window[1]}
            if in_ryohan and window
            else None
        ),
        "relation_inverted": relation_inverted,
        "effective_assessment": effective_assessment,
        "special_days_inverted": bool(inverted_specials),
        "inverted_special_labels": inverted_specials,
    }


def _leaves(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [leaf for leaf in context.get("calendar_candidates") or [context]]


def _precedence(context: dict[str, Any]) -> dict[str, Any] | None:
    assignment = (context.get("profile_calculation") or {}).get(
        "short_month_assignment"
    )
    value = assignment.get("leap_short_month_precedence") if assignment else None
    return dict(value) if value is not None else None


def _identity(context: dict[str, Any]) -> dict[str, Any] | None:
    signatures = [
        {
            "calendar_profile": leaf.get("calendar_profile"),
            "mansion_method_id": leaf.get("mansion_method_id"),
            "ruleset_id": (leaf.get("profile_calculation") or {}).get("ruleset_id"),
            "calendar_system": leaf.get("calendar_system"),
            "calendar_backend": leaf.get("calendar_backend"),
            "calendar_timezone": leaf.get("calendar_timezone"),
        }
        for leaf in _leaves(context)
    ]
    return (
        signatures[0]
        if signatures and all(s == signatures[0] for s in signatures)
        else None
    )


def _names(context: dict[str, Any]) -> set[str]:
    name = context.get("natal_su27")
    return {name} if name else set(context.get("candidate_su27s", []))


def _states(context: dict[str, Any], model: str) -> tuple[list[dict[str, Any]], bool]:
    states: list[dict[str, Any]] = []
    covered = True
    for leaf in _leaves(context):
        selected = leaf.get("calendar_day_part")
        profile = leaf.get("profile_calculation") or {}
        assignment = profile.get("short_month_assignment")
        precedence = _precedence(leaf)
        alternatives: list[tuple[str | None, str, str]] = []
        if precedence:
            records = precedence["reconstruction_calculations"]
            if len(records) != len(_MODELS) or {r["id"] for r in records} != set(
                _MODELS
            ):
                covered = False
                continue
            record = next(r for r in records if r["id"] == model)
            for half, key in (
                ("first_half", "first_half_calculation"),
                ("second_half", "second_half_calculation"),
            ):
                calc = record[key]
                if selected is None or selected == half:
                    alternatives.append((half, calc["direct_mansion"], model))
        elif assignment:
            for slot in assignment["slots"]:
                if selected is None or selected == slot["day_part"]:
                    for name in slot["candidate_mansions"]:
                        alternatives.append((slot["day_part"], name, slot["origin"]))
        else:
            alternatives.extend(
                (selected, name, "profile_result_model_independent")
                for name in sorted(_names(leaf))
            )
        actual = _names(leaf)
        if not {name for _, name, _ in alternatives}.issubset(actual):
            covered = False
        for state_half, name, origin in alternatives:
            if name in actual:
                state = {
                    "calendar_date": leaf["calendar_date"],
                    "calendar_day_part": state_half,
                    "natal_su27": name,
                    "assignment_origin": origin,
                }
                if state not in states:
                    states.append(state)
        covered = covered and bool(
            profile.get("candidate_set_complete_under_declared_reconstructions")
        )
    return states, covered and not context.get("out_of_range_calendar_dates")


def add_shared_reconstruction_support(
    first: dict[str, Any], second: dict[str, Any], analysis: dict[str, Any]
) -> dict[str, Any]:
    if not any(_precedence(leaf) for c in (first, second) for leaf in _leaves(c)):
        return analysis
    result = deepcopy(analysis)
    identity = _identity(first)
    shared: dict[str, Any] = {
        "method_id": _JOINT_METHOD,
        "status": "not_shared",
        "model_ids": list(_MODELS),
        "model_identity": identity,
        "person_half_days_independent": True,
        "source_priority_established": False,
        "historical_uniformity_established": False,
        "unconstrained_row_count": len(analysis["rows"]),
        "supported_row_count": None,
        "unsupported_row_count": None,
        "support_coverage_complete": False,
    }
    result["shared_reconstruction_analysis"] = shared
    if identity is None or identity != _identity(second):
        shared["reason"] = "profile_algorithm_source_or_calendar_identity_not_shared"
        return result
    supports: dict[tuple[str, str], list[dict[str, Any]]] = {}
    complete = analysis["candidate_set_complete_within_profile"]
    marginal_coverage: list[set[tuple[str, str]]] = [set(), set()]
    for model in _MODELS:
        left, left_complete = _states(first, model)
        right, right_complete = _states(second, model)
        complete = complete and left_complete and right_complete
        for index, states in enumerate((left, right)):
            marginal_coverage[index].update(
                (s["calendar_date"], s["natal_su27"]) for s in states
            )
        for a in left:
            for b in right:
                key = (a["natal_su27"], b["natal_su27"])
                support = {"reconstruction_id": model, "person1": a, "person2": b}
                if support not in supports.setdefault(key, []):
                    supports[key].append(support)
    for index, context in enumerate((first, second)):
        expected = {
            (leaf["calendar_date"], name)
            for leaf in _leaves(context)
            for name in _names(leaf)
        }
        complete = complete and marginal_coverage[index] == expected
    shared["support_coverage_complete"] = complete
    if result["status"] == "not_needed":
        shared["status"] = "not_needed" if complete else "incomplete"
        shared["resolved_support"] = [s for values in supports.values() for s in values]
        shared["reason"] = "resolved_mansions_do_not_establish_a_reconstruction_model"
        return result
    annotated = []
    for row in result["rows"]:
        key = (row["person1_su27"], row["person2_su27"])
        row["joint_support"] = deepcopy(supports.get(key, []))
        row["shared_reconstruction_ids"] = list(
            dict.fromkeys(s["reconstruction_id"] for s in row["joint_support"])
        )
        row["joint_support_status"] = (
            "supported"
            if row["joint_support"]
            else (
                "unsupported_within_enumerated_shared_models"
                if complete
                else "not_determined"
            )
        )
        annotated.append(row)
    result["unconstrained_rows"] = deepcopy(annotated)
    if not complete:
        shared["status"] = "incomplete"
        shared["reason"] = (
            "missing_context_or_incomplete_model_branch_coverage_no_rows_pruned"
        )
        result["candidate_set_complete_within_profile"] = False
        return result
    result["rows"] = [r for r in annotated if r["joint_support"]]
    for row in result["rows"]:
        for label in ("person1", "person2"):
            row[label + "_calendar_dates"] = list(
                dict.fromkeys(s[label]["calendar_date"] for s in row["joint_support"])
            )
    shared["status"] = "applied"
    shared["supported_row_count"] = len(result["rows"])
    shared["unsupported_row_count"] = len(annotated) - len(result["rows"])
    shared["reason"] = (
        "union_of_same_model_cartesian_products_not_cartesian_product_of_marginal_unions"
    )
    return result


def candidate_relation_analysis(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    distance_rule: DistanceRule = "symmetric",
) -> dict[str, Any]:
    """Compute directional candidate Sanjiu matrix when either person has unresolved candidates."""
    first_names = (
        [first["natal_su27"]]
        if first.get("natal_su27")
        else list(dict.fromkeys(first.get("candidate_su27s", [])))
    )
    second_names = (
        [second["natal_su27"]]
        if second.get("natal_su27")
        else list(dict.fromkeys(second.get("candidate_su27s", [])))
    )
    complete = (
        (first.get("natal_su27") is not None or bool(first_names))
        and (second.get("natal_su27") is not None or bool(second_names))
        and not first.get("out_of_range_calendar_dates")
        and not second.get("out_of_range_calendar_dates")
        and all(
            (c.get("profile_calculation") or {}).get(
                "candidate_set_complete_under_declared_reconstructions", True
            )
            for c in _leaves(first) + _leaves(second)
        )
    )
    if first.get("natal_su27") and second.get("natal_su27"):
        base = {
            "status": "not_needed",
            "candidate_set_complete_within_profile": complete,
            "rows": [],
            "calendar_date_uncertainty_remains": False,
        }
        return add_shared_reconstruction_support(first, second, base)

    def _dates_map(context: dict[str, Any]) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for leaf in _leaves(context):
            for name in _names(leaf):
                mapping.setdefault(name, [])
                if leaf["calendar_date"] not in mapping[name]:
                    mapping[name].append(leaf["calendar_date"])
        return mapping

    d1 = _dates_map(first)
    d2 = _dates_map(second)
    rows = []
    for n1 in first_names:
        for n2 in second_names:
            r12 = relation_between_su27(n1, n2, distance_rule=distance_rule)
            r21 = relation_between_su27(n2, n1, distance_rule=distance_rule)
            rows.append(
                {
                    "person1_su27": n1,
                    "person2_su27": n2,
                    "person1_to_person2": r12,
                    "person2_to_person1": r21,
                    "pair": r12["pair"],
                    "applied_to_primary": False,
                    "person1_calendar_dates": d1.get(n1, []),
                    "person2_calendar_dates": d2.get(n2, []),
                }
            )
    analysis = {
        "status": "candidate_only",
        "candidate_set_complete_within_profile": complete,
        "rows": rows,
        "calendar_date_uncertainty_remains": bool(
            first.get("calendar_candidates") or second.get("calendar_candidates")
        ),
    }
    return add_shared_reconstruction_support(first, second, analysis)
