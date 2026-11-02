"""Bind stored 1.7.0 weather hypotheses to their declared cast and conditions.

This verifier does not call the production cast, weather or control evaluator.
It shares the pinned declarative profiles and their software conventions, not
an independent interpretation of the ancient text or a new calendar authority.
The original v3 label adapter and all original study files remain unchanged.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, NoReturn

from .meihua_weather_policy_v3 import scope_aware_weather_label

PROFILE_SHA256 = "c86045852fe4898152a183ea51f1c60f570fb6205dfdb764c77fa095c4403bb7"
CONTROL_SHA256 = "e4936c492ab61da234951ce22efe1c018c664bc0e100dfdc1a9ebd06cdc8fd21"
STUDY_PINS = {
    "plan.json": "99a84a98c4d0477e8e95b1e766dab96667ad0b7d7528a13957ff24099479f7c1",
    "generated/evidence.jsonl": "bb86071afdc2a9c7264f0889684dad16eecebc64e66a031a701775dbf5d70c1a",
    "generated/forecasts.json": "4932f75eafc18f08bbe43acb336c398a65fae3141f7a34955bce769f5583f9f2",
    "generated/forecast-seal.json": "97b810c9c36e498b9db09f17f391a5f090a6525a1153abea46d0d5f01e3b8e13",
}
_TRIGRAMS = ("乾", "兑", "离", "震", "巽", "坎", "艮", "坤")
_BITS = ("111", "110", "101", "100", "011", "010", "001", "000")
_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
_WEATHER_LABELS = {"clear": "晴", "rain": "雨", "wind": "风", "thunder": "雷"}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _equal(actual: Any, expected: Any, path: str) -> None:
    # Canonical JSON also distinguishes bool from int; Python equality does not.
    if _canonical(actual) != _canonical(expected):
        raise ValueError(f"Weather evidence binding mismatch: {path}")


def _integer(value: Any, low: int, high: int, name: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Invalid integer in weather evidence: {name}")
    return value


def _many(count: int, threshold: int | None) -> bool | None:
    return count >= threshold if threshold is not None else False if count < 2 else None


def _scope_status(states: list[bool | None]) -> str:
    known = {state for state in states if state is not None}
    if known == {True} and None not in states:
        return "met_under_declared_threshold_and_scope_probes"
    if known == {False, True}:
        return "scope_unresolved"
    if None in states:
        return "pending_threshold"
    return "not_met_in_scope_probes"


def _geometry(record: dict[str, Any]) -> tuple[list[dict[str, str]], int]:
    inputs = record["input"]
    target = date.fromisoformat(record["date"])
    issue = date(
        _integer(inputs["analysis_year"], 1, 9999, "year"),
        _integer(inputs["analysis_month"], 1, 12, "month"),
        _integer(inputs["analysis_day"], 1, 31, "day"),
    )
    if target != issue + timedelta(days=1):
        raise ValueError("Weather evidence target must follow its declared issue date")
    hour = _integer(inputs["analysis_hour"], 0, 23, "hour")
    _integer(inputs["analysis_minute"], 0, 59, "minute")
    if (
        inputs["analysis_timezone"] != "Asia/Hong_Kong"
        or inputs["interpretation_topic"] != "weather"
    ):
        raise ValueError("This evidence reader supports the declared Hong Kong clock")
    actual = record["calendar_actual"]
    _equal(actual, record["calendar_expected"], "stored_calendar_comparison")
    year = _integer(actual["year"], 1, 9999, "lunar year")
    month = _integer(actual["month"], 1, 12, "lunar month")
    day = _integer(actual["day"], 1, 30, "lunar day")
    if type(actual["is_leap_month"]) is not bool:
        raise ValueError("Lunar leap flag must be a boolean")
    branch = _BRANCHES[(year - 4) % 12]
    hour_index = (hour + 1) // 2 % 12
    upper_sum = _BRANCHES.index(branch) + 1 + month + day
    total = upper_sum + hour_index + 1
    upper, lower, moving = (
        (upper_sum - 1) % 8 + 1,
        (total - 1) % 8 + 1,
        (total - 1) % 6 + 1,
    )
    _equal(
        record["seed"],
        {
            "year_branch": branch,
            "lunar_month": month,
            "lunar_day": day,
            "hour_branch": _BRANCHES[hour_index],
            "upper_number": upper,
            "lower_number": lower,
            "moving_line": moving,
        },
        "seed_from_stored_calendar_and_clock",
    )
    for name, expected in [
        ("year_branch", branch),
        ("hour_branch", _BRANCHES[hour_index]),
        ("seed_month", month),
        ("seed_day", day),
    ]:
        _equal(actual[name], expected, "calendar_actual." + name)
    base = _BITS[lower - 1] + _BITS[upper - 1]
    changed = base[: moving - 1] + str(1 - int(base[moving - 1])) + base[moving:]
    mutual_source = changed if base in {"111111", "000000"} else base
    mutual = mutual_source[1:4] + mutual_source[2:5]
    codes = {"base_code": base, "mutual_code": mutual, "changed_code": changed}
    for key, value in codes.items():
        _equal(record[key], value, key)
    slots = []
    for key, code in codes.items():
        name = key.removesuffix("_code") + "_hexagram"
        for position, bits in [("upper", code[3:]), ("lower", code[:3])]:
            slots.append(
                {
                    "path": f"meihua.{name}.{position}",
                    "trigram": _TRIGRAMS[_BITS.index(bits)],
                }
            )
    return slots, moving


def _frequency(
    name: str, views: list[dict[str, Any]], threshold: int | None
) -> dict[str, Any]:
    rows = [
        {
            "frequency_scope": view["scope"],
            "count": view["trigram_counts"][name],
            "declared_threshold": threshold,
            "condition_met": _many(view["trigram_counts"][name], threshold),
            "fact_paths": [
                s["path"] for s in view["trigram_slots"] if s["trigram"] == name
            ],
        }
        for view in views
    ]
    return {
        "status": _scope_status([r["condition_met"] for r in rows]),
        "trigram": name,
        "counting_variants": rows,
        "scope": "declared_probes_not_unique_classical_adjudication",
    }


def _controls(
    profile: dict[str, Any], views: list[dict[str, Any]], threshold: int | None
) -> list[dict[str, Any]]:
    rows = []
    for rule in profile["rules"]:
        variants = []
        for view in views:
            counts = [view["trigram_counts"][t] for t in rule["controllers"]]
            groups = [("combined_controllers", sum(counts))]
            if len(counts) > 1:
                groups.append(("either_controller_trigram", max(counts)))
            for grouping, count in groups:
                variants.append(
                    {
                        "frequency_scope": view["scope"],
                        "grouping": grouping,
                        "count": count,
                        "declared_threshold": threshold,
                        "condition_met": _many(count, threshold),
                        "controller_fact_paths": [
                            s["path"]
                            for s in view["trigram_slots"]
                            if s["trigram"] in rule["controllers"]
                        ],
                    }
                )
        affected = {
            t: tags
            for t, tags in rule["targets"].items()
            if views[0]["trigram_counts"][t]
        }
        rows.append(
            {
                "rule_id": rule["id"],
                "status": (
                    _scope_status([r["condition_met"] for r in variants])
                    if affected
                    else "not_applicable"
                ),
                **{k: rule[k] for k in ["source_id", "section", "quote", "reading"]},
                "affected_targets": affected,
                "counting_variants": variants,
                "scope": "declared_probes_not_unique_classical_adjudication",
            }
        )
    return rows


def _checks(
    conditions: dict[str, Any],
    slots: list[dict[str, str]],
    counts: Counter[str],
    context: dict[str, Any],
    views: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for name in conditions.get("present", []):
        result.append(
            {"condition": "present", "trigram": name, "met": bool(counts[name])}
        )
    for name in conditions.get("absent", []):
        result.append({"condition": "absent", "trigram": name, "met": not counts[name]})
    if "present_any" in conditions:
        names = conditions["present_any"]
        paths = [s["path"] for s in slots if s["trigram"] in names]
        result.append(
            {
                "condition": "any_present",
                "trigrams": names,
                "matched_paths": paths,
                "met": bool(paths),
            }
        )
    if "many" in conditions:
        name = conditions["many"]
        result.append(
            {
                "condition": "many",
                "trigram": name,
                "count": counts[name],
                "declared_threshold": context["many_min_count"],
                "frequency_assessment": _frequency(
                    name, views, context["many_min_count"]
                ),
                "met": _many(counts[name], context["many_min_count"]),
            }
        )
    for key in ["season", "prior_condition"]:
        if key in conditions:
            actual, required = context[key], conditions[key]
            met = (
                None
                if actual is None
                else (
                    actual in required
                    if isinstance(required, list)
                    else actual == required
                )
            )
            result.append(
                {"condition": key, "required": required, "actual": actual, "met": met}
            )
    if "pairs" in conditions:
        pairs = conditions["pairs"]
        paths = [
            slots[i]["path"].rsplit(".", 1)[0]
            for i in (0, 2, 4)
            if [slots[i]["trigram"], slots[i + 1]["trigram"]] in pairs
        ]
        result.append(
            {
                "condition": "same_hexagram_pair",
                "required_upper_lower": pairs,
                "matched_paths": paths,
                "met": bool(paths),
            }
        )
    return result


def _trace(
    rule: dict[str, Any], checks: list[dict[str, Any]], controls: list[dict[str, Any]]
) -> dict[str, Any]:
    states = [c["met"] for c in checks]
    status = (
        "not_met"
        if False in states
        else "pending_context" if None in states else "matched"
    )
    dependencies = set(
        rule["conditions"].get("present", [])
        + rule["conditions"].get("present_any", [])
    )
    if "many" in rule["conditions"]:
        dependencies.add(rule["conditions"]["many"])
    for pair in rule["conditions"].get("pairs", []):
        dependencies.update(pair)
    control_checks = []
    controlled: set[str] = set()
    conditional: set[str] = set()
    for control in controls:
        tags = {
            tag
            for trigram, values in control["affected_targets"].items()
            if trigram in dependencies
            for tag in values
            if tag in rule["tags"]
        }
        if not tags:
            continue
        control_checks.append(
            {
                "rule_id": control["rule_id"],
                "status": control["status"],
                "tags": sorted(tags),
            }
        )
        if control["status"] == "met_under_declared_threshold_and_scope_probes":
            controlled.update(tags)
        elif control["status"] in {"scope_unresolved", "pending_threshold"}:
            conditional.update(tags)
    row = {
        "rule_id": rule["id"],
        "kind": rule["kind"],
        "status": status,
        "time_scope": rule.get("time_scope", "unspecified"),
        "conditions": checks,
        "tags": rule["tags"],
        "traditional_reading": rule["reading"],
        "control_checks": control_checks,
        "qualification_reasons": [],
        "controlled_tags": sorted(controlled) if status == "matched" else [],
        "conditional_tags": (
            sorted(conditional - controlled) if status == "matched" else []
        ),
        "effective_tags": (
            [t for t in rule["tags"] if t not in controlled]
            if status == "matched"
            else []
        ),
        "effective_status": status,
        "effective_reading": rule["reading"],
        "frequency_assessment": next(
            (c["frequency_assessment"] for c in checks if c["condition"] == "many"),
            None,
        ),
    }
    if status != "matched":
        return row
    if controlled:
        row["qualification_reasons"].append("source_control")
        row["effective_status"] = "qualified_by_source_control"
        row["effective_reading"] += (
            "；其中"
            + "、".join(_WEATHER_LABELS[t] for t in sorted(controlled))
            + "象在本次明示阈值及所列计数候选下受制，不作未受制的独立判断"
        )
    if conditional - controlled:
        row["qualification_reasons"].append("unresolved_control")
        if not controlled:
            row["effective_status"] = "conditional_on_unresolved_control"
        row["effective_reading"] += (
            "；其中"
            + "、".join(_WEATHER_LABELS[t] for t in sorted(conditional - controlled))
            + "象的制约阈值或计数范围尚未确定"
        )
    frequency = row["frequency_assessment"]
    if frequency is not None and frequency["status"] == "scope_unresolved":
        row["qualification_reasons"].append("unresolved_frequency_scope")
        row["effective_status"] = (
            "conditional_on_unresolved_frequency"
            if row["effective_status"] == "matched"
            else "multiple_qualifications"
        )
        row["conditional_tags"] = sorted(
            (set(row["conditional_tags"]) | set(rule["tags"])) - controlled
        )
        counts = [v["count"] for v in frequency["counting_variants"]]
        threshold = frequency["counting_variants"][0]["declared_threshold"]
        row["effective_reading"] = (
            f"频数范围未裁定：{frequency['trigram']}在六位置计{counts[0]}、只计一次静卦则计{counts[1]}，对明示阈值{threshold}的判断有分歧；仅按六位置约定时该条为：{row['effective_reading']}"
        )
    return row


def verify_weather_trace_binding(record: dict[str, Any]) -> dict[str, Any]:
    """Verify mechanics from stored calendar labels, not their external truth."""
    try:
        weather = record["weather"]
        profile, control = weather["ruleset"], weather["control_profile"]
        if (
            _sha(_canonical(profile)) != PROFILE_SHA256
            or _sha(_canonical(control)) != CONTROL_SHA256
        ):
            raise ValueError("Weather evidence requires the pinned 1.7.0 profiles")
        _equal(
            [weather["ruleset_id"], weather["version"]],
            ["meihua_weather_v1", "1.7.0"],
            "profile_identity",
        )
        slots, moving = _geometry(record)
        supplied_context = record["input"].get("weather_context")
        context = {} if supplied_context is None else supplied_context
        if not isinstance(context, dict) or set(context) - {
            "season",
            "prior_condition",
            "many_min_count",
        }:
            raise ValueError("Unknown declared weather context")
        context = {
            k: context.get(k) for k in ["season", "prior_condition", "many_min_count"]
        }
        if context["season"] not in [
            None,
            "spring",
            "summer",
            "autumn",
            "winter",
        ] or context["prior_condition"] not in [
            None,
            "prolonged_rain",
            "prolonged_clear",
            "neither_prolonged",
        ]:
            raise ValueError("Invalid declared season or prior weather")
        threshold = context["many_min_count"]
        if threshold is not None:
            _integer(threshold, 2, 6, "many threshold")
        _equal(weather["context"], context, "context_from_input")
        _equal(weather["trigram_slots"], slots, "trigram_slots_from_geometry")
        counts: Counter[str] = Counter(s["trigram"] for s in slots)
        _equal(
            weather["trigram_counts"],
            {t: counts[t] for t in _TRIGRAMS},
            "trigram_counts",
        )
        excluded = "meihua.changed_hexagram." + ("upper" if moving <= 3 else "lower")
        views = []
        for name, selected, chosen in [
            ("six_positions", True, slots),
            (
                "five_roles_static_once",
                False,
                [s for s in slots if s["path"] != excluded],
            ),
        ]:
            totals = Counter(s["trigram"] for s in chosen)
            views.append(
                {
                    "scope": name,
                    "selected_for_main_frequency_rules": selected,
                    "slot_count": len(chosen),
                    "trigram_slots": chosen,
                    "trigram_counts": {t: totals[t] for t in _TRIGRAMS},
                    "excluded_repeated_static_path": None if selected else excluded,
                }
            )
        _equal(weather["frequency_views"], views, "frequency_views")
        controls = _controls(control, views, threshold)
        _equal(weather["controls"], controls, "controls")
        traces = [
            _trace(
                rule,
                _checks(rule["conditions"], slots, counts, context, views),
                controls,
            )
            for rule in profile["rules"]
        ]
        _equal(
            weather["rule_trace"], traces, "rule_trace_conditions_and_qualifications"
        )
        _equal(
            weather["matched_rule_ids"],
            [r["rule_id"] for r in traces if r["status"] == "matched"],
            "matched_rule_ids",
        )
        _equal(
            weather["pending_rule_ids"],
            [r["rule_id"] for r in traces if r["status"] == "pending_context"],
            "pending_rule_ids",
        )
        readings = []
        for rule, trace in zip(profile["rules"], traces, strict=True):
            if trace["status"] != "matched":
                continue
            paths: set[str] = set()
            for condition in trace["conditions"]:
                if "trigram" in condition:
                    paths.update(
                        s["path"] for s in slots if s["trigram"] == condition["trigram"]
                    )
                paths.update(condition.get("matched_paths", []))
                if condition["condition"] == "many":
                    paths.add("interpretation.weather.context.many_min_count")
                if condition["condition"] in {"season", "prior_condition"}:
                    paths.add(
                        "interpretation.weather.context." + condition["condition"]
                    )
            readings.append(
                {
                    "rule_id": trace["rule_id"],
                    "time_scope": trace["time_scope"],
                    "effective_status": trace["effective_status"],
                    "reading": trace["effective_reading"],
                    **{
                        key: trace[key]
                        for key in [
                            "controlled_tags",
                            "conditional_tags",
                            "control_checks",
                            "frequency_assessment",
                            "qualification_reasons",
                        ]
                    },
                    "fact_paths": sorted(paths),
                    **{key: rule[key] for key in ["source_id", "section", "quote"]},
                    "source_witnesses": rule.get("source_witnesses", []),
                    "textual_status": rule.get(
                        "textual_status", "fixed_transcription_only"
                    ),
                }
            )
        _equal(weather["selected_readings"], readings, "selected_readings")
        return {
            "verifier_id": "meihua_weather_trace_binding_v1",
            "mechanical_binding_verified": True,
            "rules_checked": len(traces),
            "calendar_labels_independently_authenticated": False,
            "source_semantics_independently_adjudicated": False,
            "selected_readings_verified": True,
            "extra_calendar_research_and_attribution_metadata_verified": False,
            "prediction_efficacy_established": False,
        }
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Incomplete or malformed weather binding evidence") from exc


def bound_weather_label(record: dict[str, Any]) -> dict[str, Any]:
    """Check the cast binding before applying the unchanged v3 label adapter."""
    verification = verify_weather_trace_binding(record)
    decision = scope_aware_weather_label(
        record["weather"],
        expected_profile_sha256=PROFILE_SHA256,
        expected_control_profile_sha256=CONTROL_SHA256,
    )
    _equal(record["decision"], decision, "recorded_decision")
    return {"verification": verification, "decision": decision}


def _path(directory: Path, name: str) -> Path:
    path = (directory / name).resolve()
    if not path.is_relative_to(directory):
        raise ValueError("Study evidence path escapes directory")
    return path


def _json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON evidence key")
            result[key] = value
        return result

    def invalid(value: str) -> NoReturn:
        raise ValueError("Nonfinite JSON evidence constant")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def audit_bound_weather_study(directory: Path) -> dict[str, Any]:
    """Read only the original historical forecast evidence, never outcomes."""
    directory = directory.resolve()
    files = {}
    for name in STUDY_PINS:
        if name == "generated/evidence.jsonl":
            continue
        raw = _path(directory, name).read_bytes()
        if _sha(raw) != STUDY_PINS[name]:
            raise ValueError(f"Original historical study file changed: {name}")
        files[name] = _json(raw)
    original = _path(directory, "generated/evidence.jsonl")
    compressed = _path(directory, "generated/evidence.jsonl.gz")
    if original.exists() == compressed.exists():
        raise ValueError(
            "Supply exactly one original or lossless compressed evidence file"
        )
    selected = original if original.exists() else compressed
    opener = open if selected == original else gzip.open
    digest = hashlib.sha256()
    with opener(selected, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != STUDY_PINS["generated/evidence.jsonl"]:
        raise ValueError("Original historical evidence bytes changed")
    plan = files["plan.json"]
    forecasts = files["generated/forecasts.json"]
    key = lambda row: (row["cohort"], row["scenario"], row["date"])
    indexed = {key(row): row for row in forecasts}
    expected = {
        (cohort, scenario, day)
        for cohort, days in plan["cohorts"].items()
        for scenario in plan["scenario_order"]
        for day in days
    }
    if len(forecasts) != 2008 or len(indexed) != 2008 or set(indexed) != expected:
        raise ValueError("Every original forecast date and scenario is required")
    seen = set()
    counts: dict[str, Counter[str]] = {}
    verified_digest = hashlib.sha256()
    with opener(selected, "rb") as stream:
        for line in stream:
            verified_digest.update(line)
            record = _json(line)
            identity = key(record)
            if identity not in indexed or identity in seen:
                raise ValueError("Repeated or unregistered weather evidence")
            if _sha(line.removesuffix(b"\n")) != indexed[identity]["evidence_sha256"]:
                raise ValueError("Forecast row does not bind the exact evidence bytes")
            result = bound_weather_label(record)
            label = result["decision"]["label"]
            _equal(indexed[identity]["label"], label, "forecast_label")
            counts.setdefault(identity[0] + "/" + identity[1], Counter())[label] += 1
            seen.add(identity)
    if verified_digest.hexdigest() != STUDY_PINS["generated/evidence.jsonl"]:
        raise ValueError("Weather evidence changed during mechanical verification")
    if seen != expected:
        raise ValueError("Original weather evidence cohort is incomplete")
    return {
        "verifier_id": "meihua_weather_trace_binding_v1",
        "study_id": plan["study_id"],
        "source_files_sha256": dict(STUDY_PINS),
        "evidence_records": len(seen),
        "unique_target_dates": len({identity[2] for identity in seen}),
        "raw_rule_checks": len(seen) * 40,
        "all_mechanical_bindings_verified": True,
        "original_labels_unchanged": True,
        "label_counts": {
            key: dict(sorted(value.items())) for key, value in sorted(counts.items())
        },
        "lossless_compressed_input": selected == compressed,
        "outcome_files_read": 0,
        "real_world_observations_added": 0,
        "calendar_labels_independently_authenticated": False,
        "source_semantics_independently_adjudicated": False,
        "source_timestamp_authenticated": False,
        "selected_readings_verified": True,
        "extra_calendar_research_and_attribution_metadata_verified": False,
        "legacy_time_scope_comparison_reused": True,
        "prediction_efficacy_established": False,
        "authority_certified": False,
    }
