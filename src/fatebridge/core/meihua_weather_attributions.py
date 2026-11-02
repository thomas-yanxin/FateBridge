"""Literal weather attributions and explicit seasonal clauses, not forecasts."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[1]
        / "data/meihua/weather-attributions-nlc1925-v1.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def weather_attribution_profile() -> dict[str, Any]:
    return deepcopy(_profile())


def build_weather_attributions(
    slots: list[dict[str, str]], season: str | None
) -> dict[str, Any]:
    """Use this cast's actual six positions and its confirmed season only.

    A literal attribution is not a claim that its phenomena occur together.
    A seasonal match does not resolve controls, source exceptions or outcomes.
    """
    if season not in {None, "spring", "summer", "autumn", "winter"}:
        raise ValueError("Weather attribution season must be explicit or unknown")
    if (
        len(slots) != 6
        or any(
            not isinstance(row.get("path"), str)
            or not row["path"]
            or row.get("trigram") not in set("乾兑离震巽坎艮坤")
            for row in slots
        )
        or len({row["path"] for row in slots}) != 6
    ):
        raise ValueError("Weather attributions require all six actual unique positions")
    profile = weather_attribution_profile()
    clauses = profile["clauses"]
    terms = []
    for definition in profile["terms"]:
        paths = sorted(
            row["path"] for row in slots if row["trigram"] in definition["trigrams"]
        )
        seasonal = clauses.get(definition["seasonal_clause"])
        required = seasonal["required_season"] if seasonal else None
        status = (
            "not_applicable"
            if not paths
            else (
                "no_explicit_season_clause"
                if required is None
                else (
                    "pending_context"
                    if season is None
                    else (
                        "season_matched" if season == required else "season_not_matched"
                    )
                )
            )
        )
        terms.append(
            {
                **deepcopy(definition),
                "symbol_present": bool(paths),
                "fact_paths": paths,
                "source_reading": deepcopy(clauses[definition["source_clause"]]),
                "seasonal_check": {
                    "status": status,
                    "actual_season": season,
                    "required_season": required,
                    "source_reading": deepcopy(seasonal),
                    "matched_season_is_effective_weather_verdict": False,
                    "unmatched_season_predicts_absence": False,
                },
            }
        )
    groups = []
    for key in ["metal_attributions", "li_attributions", "zhen_thunder"]:
        members = [row for row in terms if row["source_clause"] == key]
        if members[0]["symbol_present"]:
            actual = sorted(
                {
                    row["trigram"]
                    for row in slots
                    if row["path"] in members[0]["fact_paths"]
                }
            )
            groups.append(
                "本互变见"
                + "、".join(actual)
                + "，原文列“"
                + clauses[key]["quote"]
                + "”"
            )
    seasonal_text = {
        "pending_context": "季节未知，所列季令条件待确认",
        "season_matched": "已报季节与所列季令句相符",
        "season_not_matched": "已报季节不满足所列季令句",
    }
    qualifications = []
    for key in ["winter_check", "summer_check"]:
        relevant = [
            row
            for row in terms
            if row["seasonal_clause"] == key and row["symbol_present"]
        ]
        if relevant:
            qualifications.append(
                "、".join(row["term"] for row in relevant)
                + "："
                + seasonal_text[relevant[0]["seasonal_check"]["status"]]
            )
    summary = (
        "所选文明书局本天时类象补充："
        + ("；".join(groups) or "本次未见本层所列卦名，不补列这些类象")
        + ("；" + "；".join(qualifications) if qualifications else "")
        + "。本层不把日换算为晴、不把类象当成同时发生的实况；季令核对不裁定制化、例外或实际天气。"
    )
    return {
        "profile": profile,
        "terms": terms,
        "summary": summary,
        "inference_scope": "literal_attribution_and_explicit_season_check_only",
        "source_defined_categories_are_mutually_exclusive": False,
        "direct_controls_or_full_chapter_priority_adjudicated": False,
        "mapped_into_frozen_research_labels": False,
        "single_forecast": None,
        "event_datetime": None,
        "success_probability": None,
        "predictive_efficacy_established": False,
    }
