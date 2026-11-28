"""Compact table-driven Meihua topic, weather, and optional context evaluators."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from typing import Any, Literal, TypedDict, get_args

from fatebridge.core.hexagram_relations import relationship_by_role
from fatebridge.core.meihua.relations import (
    meihua_seasonal_strength,
    meihua_stage_relations,
    meihua_traditional_readings,
)
from fatebridge.core.meihua.texts import load_meihua_json, render_yaoci_text
from fatebridge.core.zhouyi import classical_hexagram

TOPICS = ("planning", "reputation", "wealth", "transaction")
JOURNEY_TOPICS = ("travel", "meeting")
HOUSEHOLD_TOPICS = ("household", "dwelling")
ALL_TOPICS = (
    *TOPICS,
    *JOURNEY_TOPICS,
    "lost_property",
    "traveler",
    *HOUSEHOLD_TOPICS,
    "marriage",
    "dining",
)
WEATHER_LABELS = {"thunder": "雷", "wind": "风", "rain": "雨", "clear": "晴"}
NEW_MANIFESTATIONS = ("gold_silver_treasure", "weapon")
CONTEXT_FIELDS = ("quiet_room", "nothing_heard", "nothing_seen")

WeatherSeason = Literal["spring", "summer", "autumn", "winter"]
WeatherPriorCondition = Literal[
    "prolonged_rain", "prolonged_clear", "neither_prolonged"
]
_WEATHER_SEASONS: tuple[WeatherSeason, ...] = get_args(WeatherSeason)
_WEATHER_PRIOR_CONDITIONS: tuple[WeatherPriorCondition, ...] = get_args(
    WeatherPriorCondition
)


class WeatherContext(TypedDict):
    season: WeatherSeason | None
    prior_condition: WeatherPriorCondition | None
    many_min_count: int | None


def normalize_weather_context(
    context: Mapping[str, object] | None,
) -> WeatherContext:
    raw = dict(context or {})
    unknown = sorted(set(raw) - {"season", "prior_condition", "many_min_count"})
    if unknown:
        raise ValueError(f"weather_context 含未声明字段：{', '.join(unknown)}")
    raw_season = raw.get("season")
    season: WeatherSeason | None = None
    if raw_season is not None:
        matched_season = next((s for s in _WEATHER_SEASONS if s == raw_season), None)
        if matched_season is None or not isinstance(raw_season, str):
            raise ValueError(f"无效的 weather_context.season：{raw_season!r}")
        season = matched_season
    raw_prior = raw.get("prior_condition")
    prior: WeatherPriorCondition | None = None
    if raw_prior is not None:
        matched_prior = next(
            (p for p in _WEATHER_PRIOR_CONDITIONS if p == raw_prior), None
        )
        if matched_prior is None or not isinstance(raw_prior, str):
            raise ValueError(f"无效的 weather_context.prior_condition：{raw_prior!r}")
        prior = matched_prior
    raw_many = raw.get("many_min_count")
    many_min_count: int | None = None
    if raw_many is not None:
        if type(raw_many) is not int or not 2 <= raw_many <= 6:
            raise ValueError("weather_context.many_min_count 须为 2 至 6 的整数")
        many_min_count = raw_many
    return {
        "season": season,
        "prior_condition": prior,
        "many_min_count": many_min_count,
    }


def _topic_profile(topic: str) -> dict[str, Any]:
    mapping = {
        "dining": "dining-nlc1925-v1.json",
        "marriage": "marriage-nlc1925-v1.json",
        "household": "households-nlc1925-v1.json",
        "dwelling": "households-nlc1925-v1.json",
        "traveler": "traveler-nlc1925-v1.json",
        "lost_property": "lost-property-nlc1925-v1.json",
        "travel": "journeys-nlc1925-v1.json",
        "meeting": "journeys-nlc1925-v1.json",
    }
    return load_meihua_json(mapping.get(topic, "topics-nlc1925-v1.json"))


def build_general_casting_readings(
    cast: dict[str, Any], month_branch: str | None
) -> dict[str, Any]:
    """Build compact per-candidate readings when counting variants differ."""
    readings = []
    for index, variant in enumerate(cast.get("counting_variants", [])):
        prefix = f"meihua.counting_variants.{index}"
        stages = deepcopy(variant["stage_relations"])
        seasonal = meihua_seasonal_strength(variant, month_branch, fact_prefix=prefix)
        stage_readings, traditional = meihua_traditional_readings(stages, seasonal)
        chapter = classical_hexagram(variant["base_code"])
        verse = next(
            row for row in chapter["yaoci"] if row["position"] == variant["moving_line"]
        )
        readings.append(
            {
                "line_sum_basis": variant["line_sum_basis"],
                "selected": variant["selected"],
                "moving_line": variant["moving_line"],
                "base_code": variant["base_code"],
                "changed_code": variant["changed_code"],
                "mutual_code": variant["mutual_code"],
                "body": variant["body"],
                "use": variant["use"],
                "body_use_relation": variant["body_use_relation"],
                "fact_prefix": prefix,
                "stage_relations": stages,
                "seasonal_strength": seasonal,
                "traditional_stage_readings": stage_readings,
                "traditional_judgement": traditional,
                "classical_text_reference": {
                    "moving_yaoci": verse,
                    "moving_yaoci_rendering": render_yaoci_text(verse["text"]),
                },
            }
        )
    changed_fields = [
        key
        for key in (
            "moving_line",
            "changed_code",
            "mutual_code",
            "body",
            "use",
            "body_use_relation",
        )
        if len({row[key] for row in readings}) > 1
    ]
    return {
        "casting_readings": readings,
        "casting_comparison": {
            "status": (
                "different_interpretation_facts"
                if changed_fields
                else (
                    "no_counting_variants"
                    if not readings
                    else "same_selected_interpretation_facts"
                )
            ),
            "candidate_count": len(readings),
            "changed_fields": changed_fields,
        },
    }


def general_casting_summary(readings: list[dict[str, Any]]) -> str:
    """Summarize distinct counting candidates concisely."""
    parts = ["各候选分列："]
    for row in readings:
        label = "原数口径" if row["line_sum_basis"] == "raw_counts" else "卦序数口径"
        selected = "（本次所选）" if row["selected"] else ""
        display = row["classical_text_reference"]["moving_yaoci_rendering"][
            "display_text"
        ]
        verse_text = display if display is not None else "〔转录标记未解析〕"
        parts.append(
            f"{label}{selected}：动{row['moving_line']}爻，原体{row['body']}、用{row['use']}。"
            f"{row['traditional_judgement']} 爻辞：{verse_text} "
        )
    return "".join(parts)


def build_topic_interpretation(cast: dict[str, Any], topic: str) -> dict[str, Any]:
    """Build compact topic clause reading without static 86 KB NLC1925 walls."""
    if topic not in ALL_TOPICS:
        raise ValueError("Select one of the published Meihua topic chapters")
    profile = _topic_profile(topic)
    chapter = profile["topics"][topic]
    stages = meihua_stage_relations(cast)
    initial = stages[0]
    rule = next(
        r
        for r in profile["rules"]
        if r["topic"] == topic and r["relation"] == initial["relation"]
    )
    selected: dict[str, Any] = {
        "topic": topic,
        "label": chapter["label"],
        "section": chapter["section"],
        "body": initial["body"],
        "use": initial["trigram"],
        "relation": initial["relation"],
        "clause_id": rule["id"],
        "quote": rule["quote"],
        "reading": rule["reading"],
    }
    if topic == "lost_property":
        lp = load_meihua_json("lost-property-nlc1925-v1.json")
        line = cast["seed"]["moving_line"]
        pos = "lower" if line <= 3 else "upper"
        trigram = cast["changed_hexagram"][pos]["name"]
        loc_rule = next(r for r in lp["location_rules"] if r["trigram"] == trigram)
        selected["changed_use_location"] = {
            "trigram": trigram,
            "direction_symbol": loc_rule["direction_symbol"],
            "place_symbols": list(loc_rule["place_symbols"]),
        }

    seasonal = cast.get("seasonal_strength")
    stage_readings, _ = meihua_traditional_readings(stages, seasonal)
    branch = seasonal["month_branch"] if seasonal is not None else None
    alternatives = build_general_casting_readings(cast, branch)
    reference = classical_hexagram(cast["base_hexagram"]["binary_code"])
    line = cast["seed"]["moving_line"]
    verse = next(v for v in reference["yaoci"] if v["position"] == line)
    summary = (
        f"按《{selected['section']}》，原体{selected['body']}、用{selected['use']}"
        f"为{selected['relation']}；原文“{selected['quote']}”。{selected['reading']}。"
    )
    return {
        "interpretation_topic": topic,
        "weather": None,
        "question_domain": {"key": topic, "label": selected["label"]},
        "topic_reading": selected,
        "traditional_stage_readings": stage_readings,
        "traditional_judgement": summary,
        "classical_text_reference": {
            "moving_yaoci": verse,
            "moving_yaoci_rendering": render_yaoci_text(verse["text"]),
        },
        **alternatives,
        "comprehensive_judgement": summary,
    }


def _weather_frequency_views(
    slots: list[dict[str, str]], moving_line: int, *, fact_prefix: str = "meihua"
) -> list[dict[str, Any]]:
    static_position = "upper" if moving_line <= 3 else "lower"
    repeated_static = f"{fact_prefix}.changed_hexagram.{static_position}"
    five_slots = [row for row in slots if row["path"] != repeated_static]
    variants = []
    for name, selected, rows in (
        ("six_positions", True, slots),
        ("five_roles_static_once", False, five_slots),
    ):
        counts = Counter(row["trigram"] for row in rows)
        variants.append(
            {
                "scope": name,
                "selected_for_main_frequency_rules": selected,
                "slot_count": len(rows),
                "trigram_slots": rows,
                "trigram_counts": {t: counts[t] for t in "乾兑离震巽坎艮坤"},
            }
        )
    return variants


def _assess_weather_controls(
    frequency_views: list[dict[str, Any]], threshold: int | None
) -> list[dict[str, Any]]:
    profile = load_meihua_json("weather-controls-v1.json")
    results = []
    for rule in profile["rules"]:
        variants = []
        for view in frequency_views:
            controller_counts = [view["trigram_counts"][t] for t in rule["controllers"]]
            groupings = {"combined_controllers": sum(controller_counts)}
            if len(controller_counts) > 1:
                groupings["either_controller_trigram"] = max(controller_counts)
            for grouping, count in groupings.items():
                variants.append(
                    {
                        "frequency_scope": view["scope"],
                        "grouping": grouping,
                        "count": count,
                        "condition_met": (
                            count >= threshold
                            if threshold is not None
                            else False if count < 2 else None
                        ),
                    }
                )
        affected = {
            trigram: tags
            for trigram, tags in rule["targets"].items()
            if frequency_views[0]["trigram_counts"][trigram] > 0
        }
        states = [v["condition_met"] for v in variants]
        if not affected:
            status = "not_applicable"
        elif all(state is True for state in states):
            status = "met_under_declared_threshold_and_scope_probes"
        elif True in states and False in states:
            status = "scope_unresolved"
        elif None in states:
            status = "pending_threshold"
        else:
            status = "not_met_in_scope_probes"
        results.append(
            {
                "rule_id": rule["id"],
                "status": status,
                "affected_targets": affected,
            }
        )
    return results


def _build_weather_one(
    meihua: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    fact_prefix: str = "meihua",
) -> dict[str, Any]:
    confirmed = normalize_weather_context(context)
    profile = load_meihua_json("weather-v1.json")
    hexagrams = [
        (key, meihua[key])
        for key in ("base_hexagram", "mutual_hexagram", "changed_hexagram")
    ]
    slots = [
        {"path": f"{fact_prefix}.{key}.{position}", "trigram": value[position]["name"]}
        for key, value in hexagrams
        for position in ("upper", "lower")
    ]
    counts = Counter(row["trigram"] for row in slots)
    frequency_views = _weather_frequency_views(
        slots, meihua["seed"]["moving_line"], fact_prefix=fact_prefix
    )
    controls = _assess_weather_controls(frequency_views, confirmed["many_min_count"])
    traces: list[dict[str, Any]] = []
    for rule in profile["rules"]:
        conditions = rule["conditions"]
        checks: list[dict[str, Any]] = []
        for name in conditions.get("present", []):
            checks.append(
                {"condition": "present", "trigram": name, "met": counts[name] > 0}
            )
        for name in conditions.get("absent", []):
            checks.append(
                {"condition": "absent", "trigram": name, "met": counts[name] == 0}
            )
        if "present_any" in conditions:
            names = conditions["present_any"]
            matched_paths = [s["path"] for s in slots if s["trigram"] in names]
            checks.append(
                {
                    "condition": "any_present",
                    "trigrams": names,
                    "matched_paths": matched_paths,
                    "met": bool(matched_paths),
                }
            )
        if "many" in conditions:
            name = conditions["many"]
            threshold = confirmed["many_min_count"]
            c_val = counts[name]
            checks.append(
                {
                    "condition": "many",
                    "trigram": name,
                    "count": c_val,
                    "declared_threshold": threshold,
                    "met": (
                        c_val >= threshold
                        if threshold is not None
                        else False if c_val < 2 else None
                    ),
                }
            )
        for name in ("season", "prior_condition"):
            if name in conditions:
                actual = (
                    confirmed["season"]
                    if name == "season"
                    else confirmed["prior_condition"]
                )
                required = conditions[name]
                checks.append(
                    {
                        "condition": name,
                        "required": required,
                        "actual": actual,
                        "met": (
                            (
                                actual in required
                                if name == "season" and isinstance(required, list)
                                else actual == required
                            )
                            if actual is not None
                            else None
                        ),
                    }
                )
        if "pairs" in conditions:
            matched_paths = [
                f"{fact_prefix}.{key}"
                for key, value in hexagrams
                if [value["upper"]["name"], value["lower"]["name"]]
                in conditions["pairs"]
            ]
            checks.append(
                {
                    "condition": "same_hexagram_pair",
                    "matched_paths": matched_paths,
                    "met": bool(matched_paths),
                }
            )
        states = [row["met"] for row in checks]
        status = (
            "not_met"
            if False in states
            else "pending_context" if None in states else "matched"
        )
        dependencies = set(conditions.get("present", []))
        dependencies.update(conditions.get("present_any", []))
        if "many" in conditions:
            dependencies.add(conditions["many"])
        for pair in conditions.get("pairs", []):
            dependencies.update(pair)
        controlled: set[str] = set()
        for control in controls:
            if control["status"] == "met_under_declared_threshold_and_scope_probes":
                for trigram, tags in control["affected_targets"].items():
                    if trigram in dependencies:
                        controlled.update(t for t in tags if t in rule["tags"])
        effective_status = (
            "qualified_by_source_control"
            if status == "matched" and controlled
            else status
        )
        traces.append(
            {
                "rule_id": rule["id"],
                "kind": rule["kind"],
                "status": status,
                "effective_status": effective_status,
                "time_scope": rule.get("time_scope", "unspecified"),
                "conditions": checks,
                "tags": rule["tags"],
                "effective_reading": rule["reading"],
            }
        )

    matched = [row for row in traces if row["status"] == "matched"]
    pending = [row["rule_id"] for row in traces if row["status"] == "pending_context"]
    readings = "".join(row["effective_reading"] + "。" for row in matched)
    summary = "按卷二天时占，不以体用生克判断天气；" + (
        readings or "本次未命中已实现的条件条款。"
    )
    return {
        "interpretation_topic": "weather",
        "question_domain": {"key": "weather", "label": "天时"},
        "weather": {
            "ruleset_id": profile["id"],
            "version": profile["version"],
            "context": confirmed,
            "trigram_counts": {name: counts[name] for name in "乾兑离震巽坎艮坤"},
            "controls": controls,
            "matched_rule_ids": [row["rule_id"] for row in matched],
            "pending_rule_ids": pending,
            "single_forecast": None,
        },
        "comprehensive_judgement": summary,
    }


def build_weather_interpretation(
    meihua: dict[str, Any], context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Evaluate classical weather symbols without body/use."""
    return _build_weather_one(meihua, context)


def _external_reading(
    body: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    fact_prefix: str,
    interpretation_prefix: str,
) -> dict[str, Any]:
    profile = load_meihua_json("external-manifestations-nlc1925-v1.json")
    reversal = load_meihua_json("omen-reversal-nlc1925-v1.json")
    rows = []
    parts = []
    for index, observation in enumerate(observations):
        kind = observation["manifestation"]
        category = profile["manifestations"].get(kind) or reversal[
            "manifestations"
        ].get(kind)
        if category is None:
            raise ValueError("Unknown external manifestation category")
        raw = relationship_by_role(body["element"], category["element"])
        rule = next(
            (
                r
                for r in profile["rules"]
                if r["manifestation"] == kind and r["body_element"] == body["element"]
            ),
            None,
        )
        rows.append(
            {
                "record_index": index,
                "manifestation": kind,
                "reported_fact_path": f"{interpretation_prefix}.external_omens.reported_observations.{index}",
                "body": body["name"],
                "body_element": body["element"],
                "body_fact_path": fact_prefix + ".body_trigram",
                "external_element": category["element"],
                "raw_relation_to_body": raw,
                "qualification": (
                    rule["qualification"] if rule else "not_addressed_in_selected_pairs"
                ),
                "rule_id": rule["id"] if rule else None,
                "quote": rule["quote"] if rule else None,
            }
        )
        parts.append(
            f"外应{index + 1}({category['description']}，{category['element']})对原体{body['name']}为{raw}。"
        )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "reported_observations": deepcopy(observations),
        "observations": rows,
        "summary": "".join(parts),
    }


def apply_external_omens(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    observations: list[dict[str, Any]] | None,
) -> None:
    """Attach compact external-omen qualifications when observations are supplied."""
    interpretation["external_omens"] = None
    if observations is None:
        return
    selected = _external_reading(
        cast["body_trigram"],
        observations,
        fact_prefix="meihua",
        interpretation_prefix="interpretation",
    )
    interpretation["external_omens"] = selected
    for index, row in enumerate(interpretation.get("casting_readings") or []):
        row["external_omens"] = _external_reading(
            cast["counting_variants"][index]["body_trigram"],
            observations,
            fact_prefix=f"meihua.counting_variants.{index}",
            interpretation_prefix=f"interpretation.casting_readings.{index}",
        )
    interpretation["comprehensive_judgement"] += selected["summary"]


def _motion_reading(
    external: dict[str, Any] | None,
    *,
    observer_activity: str | None,
    observer_fact_path: str,
) -> dict[str, Any]:
    profile = load_meihua_json("motion-nlc1925-v1.json")
    rules = {r["id"]: r for r in profile["rules"]}
    orientation_source = profile["orientation_reference"]
    observer_rule = (
        rules.get("observer_" + observer_activity) if observer_activity else None
    )
    observer = {
        "activity": observer_activity,
        "fact_path": observer_fact_path if observer_activity else None,
        "rule_id": observer_rule["id"] if observer_rule else None,
        "quote": observer_rule["quote"] if observer_rule else None,
    }
    rows = []
    observations = (
        zip(external["reported_observations"], external["observations"], strict=True)
        if external
        else ()
    )
    for index, (observation, qualification) in enumerate(observations):
        motion = observation.get("motion")
        orientation = observation.get("orientation")
        orientation_clauses = []
        for clause in orientation_source["clauses"]:
            orientation_met = (
                False
                if motion == "stationary"
                else (
                    None
                    if orientation is None
                    else orientation == clause["orientation"]
                )
            )
            relation_met = qualification["raw_relation_to_body"] == clause["relation"]
            orientation_clauses.append(
                {
                    **clause,
                    "orientation_condition_met": orientation_met,
                    "symbolic_relation_condition_met": relation_met,
                    "cross_chapter_qualification_met": None,
                    "full_clause_applies": (
                        False if orientation_met is False or not relation_met else None
                    ),
                }
            )
        rows.append(
            {
                "record_index": index,
                "orientation": orientation,
                "motion": motion,
                "omen_valence": None,
                "event_time": None,
                "orientation_clauses": orientation_clauses,
            }
        )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "orientation_source": {
            "section": orientation_source["section"],
            "edition_status": orientation_source["edition_status"],
        },
        "observer": observer,
        "external_motion": rows,
        "summary": "",
    }


def apply_motion_context(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    *,
    observer_activity: str | None = None,
    observer_fact_path: str = "analysis_context.observer_activity",
) -> None:
    """Attach compact motion/orientation context only when activity or omens are supplied."""
    interpretation["motion_context"] = None
    if observer_activity not in {None, "seated", "walking", "standing"}:
        raise ValueError("Unknown reported observer activity")
    if interpretation["interpretation_topic"] == "weather":
        if observer_activity is not None:
            raise ValueError("Selected human motion clauses do not apply to weather")
        return
    if observer_activity is None and interpretation.get("external_omens") is None:
        return
    interpretation["motion_context"] = _motion_reading(
        interpretation.get("external_omens"),
        observer_activity=observer_activity,
        observer_fact_path=observer_fact_path,
    )
    for candidate in interpretation.get("casting_readings") or []:
        candidate["motion_context"] = _motion_reading(
            candidate.get("external_omens"),
            observer_activity=observer_activity,
            observer_fact_path=observer_fact_path,
        )


def apply_observation_context(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    context: dict[str, Any] | None,
    *,
    context_fact_path: str,
) -> None:
    """Attach quiet-context evaluation only when observation_context is supplied."""
    interpretation["observation_context"] = None
    if context is None or interpretation["interpretation_topic"] == "weather":
        return
    values = [context.get(key) for key in CONTEXT_FIELDS]
    matches = (
        False
        if any(v is False for v in values)
        else True if all(v is True for v in values) else None
    )
    interpretation["observation_context"] = {
        "context_fact_path": context_fact_path,
        "reported_context": deepcopy(context),
        "matches_declared_source_conditions": matches,
        "status": (
            "declared_conditions_met"
            if matches is True
            else (
                "declared_conditions_not_met"
                if matches is False
                else "pending_declared_conditions"
            )
        ),
    }


def reported_day_qi_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_candidate_id": "caller_reported",
        "candidates": [
            {
                "id": "caller_reported",
                "date": None,
                "ganzhi": None,
                "day_branch": context["day_branch"],
            }
        ],
    }


def apply_day_qi(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    day_context: dict[str, Any] | None,
    *,
    declared_fact_path: str | None = None,
) -> None:
    """Attach compact day-branch element relation to body trigram."""
    interpretation["day_qi"] = None
    if day_context is None or interpretation["interpretation_topic"] == "weather":
        return
    branch_elements = dict(zip("子丑寅卯辰巳午未申酉戌亥", "水土木木土火火土金金土水"))
    body_elem = cast["body_trigram"]["element"]
    selected_id = day_context["selected_candidate_id"]
    selected = next(c for c in day_context["candidates"] if c["id"] == selected_id)
    day_elem = branch_elements[selected["day_branch"]]
    interpretation["day_qi"] = {
        "selected_candidate_id": selected_id,
        "day_branch": selected["day_branch"],
        "day_element": day_elem,
        "ganzhi": selected.get("ganzhi"),
        "relation_to_body": relationship_by_role(body_elem, day_elem),
        "declared_fact_path": declared_fact_path,
    }


def apply_situational_responses(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    context: dict[str, Any] | None,
    *,
    context_fact_path: str,
) -> None:
    """Attach compact situational response trigram candidates only when supplied."""
    interpretation["response_context"] = None
    if context is None or interpretation["interpretation_topic"] == "weather":
        return
    profile = load_meihua_json("situational-responses-nlc1925-v1.json")
    body = cast["body_trigram"]
    rows = []
    for family in ("querent_position", "weather", "setting", "human"):
        supplied = context.get(family)
        if supplied is None:
            continue
        categories = (
            [supplied["direction"]] if family == "querent_position" else supplied
        )
        for category in categories:
            trigrams = profile["tables"][family][category]
            rows.append(
                {
                    "family": family,
                    "category": category,
                    "trigram_candidates": [
                        {
                            "trigram": t,
                            "element": profile["trigram_elements"][t],
                            "relation_to_body": relationship_by_role(
                                body["element"], profile["trigram_elements"][t]
                            ),
                        }
                        for t in trigrams
                    ],
                }
            )
    interpretation["response_context"] = {
        "context_fact_path": context_fact_path,
        "responses": rows,
    }


def apply_reputation_supplement(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    context_fact_path: str = "analysis_context.reputation_context",
) -> None:
    """Attach compact reputation timing/direction lookup when topic is reputation."""
    interpretation["reputation_supplement"] = None
    if interpretation["interpretation_topic"] != "reputation":
        return
    profile = load_meihua_json("reputation-nlc1925-v1.json")
    body_name = cast["body_trigram"]["name"]
    interpretation["reputation_supplement"] = {
        "context_fact_path": context_fact_path if context is not None else None,
        "reported_context": deepcopy(context),
        "time_class": profile["time_classes"][body_name],
        "fangdao_class": profile["fangdao_classes"][body_name],
    }


def apply_stage_emphasis(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    *,
    matter_scenario: str | None = None,
    scenario_fact_path: str = "analysis_context.matter_scenario",
) -> None:
    """Attach compact scenario tag only when matter_scenario is declared."""
    if matter_scenario is None or interpretation["interpretation_topic"] == "weather":
        return
    interpretation["stage_emphasis"] = {
        "matter_scenario": matter_scenario,
        "scenario_fact_path": scenario_fact_path,
    }


def apply_postheaven_count_reference(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
) -> None:
    """No-op lightweight placeholder for services/divination.py compatibility."""
    return None


def apply_trigram_relation_symbols(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
) -> None:
    """No-op lightweight placeholder (13 KB static wall stripped)."""
    return None


def apply_qi_day_timing_references(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
) -> None:
    """No-op lightweight placeholder (static wall stripped)."""
    return None


def apply_qi_branch_timing_references(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
) -> None:
    """No-op lightweight placeholder (static wall stripped)."""
    return None
