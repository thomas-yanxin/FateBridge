"""Bind Heluo's consumed boundaries to the shared civil-year term window."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from fatebridge.core.almanac import (
    _term_window,
    get_solar_term_environment_key,
    localize_datetime,
    require_calculated_solar_term,
)
from fatebridge.utils.errors import NumerologySourceError

POLICY_ID = "heluo_shared_solar_context_v1"
LI_TERMS = frozenset({"立春", "立夏", "立秋", "立冬"})


def resolve_solar_context(anchor: datetime, zone: str) -> dict[str, Any]:
    """Retain exactly the current term, last solstice and next four-li used.

    The input's local civil year selects the canonical adjacent-year allowance.
    Neither a UTC year crossing nor a guarded cached year authorizes a separate
    out-of-range public year-grid request under an explicit model.
    """
    local = localize_datetime(anchor, zone)
    if local.utcoffset() is None:
        raise ValueError("节气上下文需要带时区的真实时刻。")
    at = local.astimezone(timezone.utc)
    environment = get_solar_term_environment_key(year=local.year)
    window = _term_window(local, zone)
    before = [t for t in window if t.moment.astimezone(timezone.utc) <= at]
    after = [t for t in window if t.moment.astimezone(timezone.utc) > at]
    try:
        selected = (
            ("current_term", before[-1]),
            (
                "preceding_solstice",
                next(t for t in reversed(before) if t.name in {"冬至", "夏至"}),
            ),
            ("next_four_li", next(t for t in after if t.name in LI_TERMS)),
        )
        for _, term in selected:
            require_calculated_solar_term(term)
    except (IndexError, StopIteration, RuntimeError) as exc:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc
    if get_solar_term_environment_key(year=local.year) != environment:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict")
    return {
        "policy_id": POLICY_ID,
        "context_local_year": local.year,
        "context_timezone": zone,
        "birth_instant_utc": at.isoformat(),
        "dependencies": [
            {
                "role": role,
                "record": term.as_dict(),
                "instant_utc": term.moment.astimezone(timezone.utc).isoformat(),
                "ephemeris_retflags": list(term.ephemeris_retflags),
                "ephemeris_library_version": term.ephemeris_library_version,
            }
            for role, term in selected
        ],
        "environment_unchanged_at_observation_points": True,
        "calendar_context_match": None,
        "scope": "Same local-civil-year window as shared year/month calculation. Actual consumed providers/models are retained; neighbouring roots do not extend public model years. Before/after environment observations do not prove atomic file reads, independent accuracy or historical UTC.",
    }


def bind_solar_context(solar: dict, calendar_context: dict, birth: datetime) -> None:
    try:
        if birth.utcoffset() is None:
            raise ValueError("出生时刻必须带时区。")
        context = solar["boundary_context"]
        current, solstice, following = context["dependencies"]
        instant = birth.astimezone(timezone.utc)
        end = datetime.fromisoformat(following["instant_utc"])
        start = end - timedelta(days=18)
        if (
            [r["role"] for r in context["dependencies"]]
            != ["current_term", "preceding_solstice", "next_four_li"]
            or current["record"] != calendar_context.get("current_solar_term")
            or context["context_timezone"] != calendar_context.get("timezone")
            or context["context_local_year"]
            != localize_datetime(birth, context["context_timezone"]).year
            or datetime.fromisoformat(context["birth_instant_utc"]) != instant
            or datetime.fromisoformat(solar["anchor_utc"]) != instant
            or context["environment_unchanged_at_observation_points"] is not True
            or current["record"]["name"] != solar["term"]
            or solstice["record"]["name"] not in {"冬至", "夏至"}
            or following["record"]["name"] not in LI_TERMS
            or solar["yang_ling"] != (solstice["record"]["name"] == "冬至")
            or datetime.fromisoformat(current["instant_utc"]) > instant
            or datetime.fromisoformat(solstice["instant_utc"]) > instant
            or end <= instant
            or datetime.fromisoformat(solar["tuyong_start_utc"]) != start
            or datetime.fromisoformat(solar["tuyong_end_utc"]) != end
            or solar["tuyong"] != (start <= instant < end)
        ):
            raise ValueError("所用节气上下文、出生瞬间与分类结果不一致。")
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc
    context["calendar_context_match"] = True


def bind_seasonal_context(solar: dict, seasonal: dict) -> None:
    try:
        context = solar["boundary_context"]
        solstice = context["dependencies"][1]
        rows = [
            r
            for r in seasonal["seasonal_windows"]
            if r["start_term"] == solstice["record"]["name"]
        ]
        if (
            seasonal["context_local_year"] != context["context_local_year"]
            or seasonal["context_timezone"] != context["context_timezone"]
            or seasonal["birth_instant_utc"] != context["birth_instant_utc"]
            or len(rows) != 1
            or rows[0]["start_source"] != solstice["record"]
        ):
            raise ValueError("二数时令与化工／阴阳令不是同一节气上下文。")
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc


def attach_solar_context(evidence: dict, solar: dict) -> None:
    from fatebridge.core.numerology_solar_sources import attach_solar_sources

    evidence["rulesets"].append(
        {
            "ruleset_id": POLICY_ID,
            "version": "1.0.0",
            "source_title": "现代节气黄经交点上下文及河洛至点／四立取用",
            "source_url": None,
            "source_status": "actual_consumed_boundary_provenance; not_independent_accuracy_or_classical_calendar_certification",
        }
    )
    evidence["rule_trace"].append(
        {
            "rule_id": POLICY_ID,
            "source_section": "Shared modern solar context; current term, preceding solstice and next four-li",
            "facts": deepcopy(solar["boundary_context"]),
        }
    )
    attach_solar_sources(evidence, POLICY_ID, solar["boundary_context"]["dependencies"])


def solar_context_snapshot(context: dict) -> str:
    lines = ["[所用节气与至点来源]"]
    labels = {
        "current_term": "当前节气",
        "preceding_solstice": "最近至点",
        "next_four_li": "下一四立",
    }
    for row in context["dependencies"]:
        term = row["record"]
        lines.append(
            f"{labels[row['role']]}：{term['name']}，UTC {row['instant_utc']}；来源{term['resolution_provider']}／{term['ephemeris_model']}。"
        )
    lines.append(
        f"按民用时区{context['context_timezone']}的{context['context_local_year']}年上下文读取；相邻年边界不扩展公开模型年份，数值分辨率不等于实际精度认证。"
    )
    return "\n".join(lines)
