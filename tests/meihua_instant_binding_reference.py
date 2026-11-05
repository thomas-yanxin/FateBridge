"""Pre-change clock literals and portable JSON-shaped fault injections."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_instant_binding_v1"
MANIFEST_SHA256 = "16b58b953f0ec190ab604fc1ea81de67eea519d1bf805a7972063ee2c9b4d0ad"


def load():
    raw = (FOLDER / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    for name, expected in json.loads(raw)["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == expected
    cases = json.loads((FOLDER / "cases25.json").read_bytes())
    protocol = json.loads((FOLDER / "protocol.json").read_bytes())
    assert len(cases) == 25 and len(protocol["faults"]) == 34
    assert len({r["id"] for r in cases}) == 25
    return cases, protocol


def new_result(case):
    from fatebridge.application.meihua_clock_binding import supplied_clock_components
    from fatebridge.core.requests.divination import MeihuaAnalysisRequest
    from fatebridge.services.divination import calculate_meihua_analysis

    request = MeihuaAnalysisRequest(**case["arguments"])
    result = calculate_meihua_analysis(
        **case["arguments"],
        _clock_supplied_components=supplied_clock_components(request),
    )
    assert "error" not in result, (case["id"], result)
    return request, result


def clock_of(result):
    return result["meihua"]["calendar_policy"]["civil_clock_resolution"]


def clock_aliases(result, clock):
    for cast in [
        result["meihua"],
        result["calendar_context"]["lunar_calendar"]["meihua"],
    ]:
        cast["calendar_policy"]["civil_clock_resolution"] = clock
        for row in cast["rule_trace"]:
            if row["rule_id"] == "civil_clock_resolution":
                row["result"] = clock


def shift(value, **kwargs):
    return (datetime.fromisoformat(value) + timedelta(**kwargs)).isoformat()


def mutate(value, name):
    # JSON round trip avoids relying on Python dictionary alias accidents.
    result = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    clock = clock_of(result)
    ac, cc = result["analysis_context"], result["calendar_context"]
    month = cc["bazi_month_boundary"]
    if name == "clock_UTC_one_day":
        clock["instant_utc"] = shift(clock["instant_utc"], days=1)
        clock["input_components"]["nominal_instant_utc"] = clock["instant_utc"]
    elif name == "analysis_UTC_one_day":
        ac["civil_instant_utc"] = shift(ac["civil_instant_utc"], days=1)
    elif name == "analysis_wall_one_day":
        ac["analysis_datetime"] = shift(ac["analysis_datetime"], days=1)
    elif name == "calendar_wall_one_day":
        cc["solar_datetime"] = shift(cc["solar_datetime"], days=1)
    elif name == "month_comparison_one_day":
        month["comparison_datetime"] = shift(month["comparison_datetime"], days=1)
    elif name == "month_elapsed_since_plus_hour":
        month["elapsed_seconds_since_start"] += 3600
    elif name == "month_elapsed_until_minus_hour":
        month["elapsed_seconds_until_next"] -= 3600
    elif name == "month_elapsed_basis_wall":
        month["elapsed_basis"] = "wall_clock_seconds"
    elif name == "clock_zone_changed":
        clock["timezone"] = "UTC"
    elif name == "analysis_zone_changed":
        ac["timezone"] = "UTC"
    elif name == "calendar_zone_changed":
        cc["timezone"] = "UTC"
    elif name == "resolved_offset_changed":
        clock["resolved_utc_offset"] = "+09:00"
    elif name == "analysis_offset_changed":
        ac["civil_utc_offset"] = "+09:00"
    elif name == "fold_changed":
        clock["fold"] = 1
    elif name == "fold_bool":
        clock["fold"] = False
    elif name == "fold_later_changed_to_earlier":
        clock["fold"] = 0
    elif name == "timezone_provider_changed":
        clock["timezone_rules"]["provider"] = "unverified_provider"
    elif name == "clock_method_changed":
        clock["method"] = "unverified_clock"
    elif name == "clock_precision_exaggerated":
        clock["clock_label_precision"] = (
            "supplied_civil_second; historical_offset_seconds_preserved"
        )
    elif name == "old_second_value_changed":
        clock["input_second"]["value"] += 1
    elif name == "old_second_record_removed":
        del clock["input_second"]
    elif name == "old_second_record_invented":
        clock["input_second"] = {
            "ruleset_id": "meihua_civil_second_input_v1",
            "version": "1.0.0",
            "rule_kind": "software_convention",
            "value": 0,
            "seconds_enter_cast_seed": False,
            "input_precision_certifies_accuracy": False,
            "original_text_uniquely_prescribes_seconds": False,
        }
    elif name in {"trace_timezone_changed", "trace_offset_changed"}:
        key = "timezone" if name == "trace_timezone_changed" else "utc_offset"
        for cast in [result["meihua"], cc["lunar_calendar"]["meihua"]]:
            for row in cast["rule_trace"]:
                if row["rule_id"] == "civil_clock_resolution":
                    row["inputs"][key] = "UTC" if key == "timezone" else "+09:00"
    elif name == "month_start_timestamp_changed":
        month["start_term"]["datetime_with_offset"] = shift(
            month["start_term"]["datetime_with_offset"], days=1
        )
    elif name == "month_next_timestamp_changed":
        month["next_term"]["datetime_with_offset"] = shift(
            month["next_term"]["datetime_with_offset"], days=-100
        )
    elif name == "coherent_wrong_offset_and_UTC":
        local = datetime.fromisoformat(clock["local_datetime"]).replace(
            tzinfo=timezone(timedelta(hours=7))
        )
        actual = local.astimezone(timezone.utc)
        clock.update(
            timezone="+07:00",
            local_datetime=local.isoformat(),
            instant_utc=actual.isoformat(),
            resolved_utc_offset="+07:00",
        )
        clock["input_components"].update(
            nominal_civil_datetime=local.isoformat(),
            nominal_instant_utc=actual.isoformat(),
        )
        ac.update(
            timezone="+07:00",
            civil_instant_utc=actual.isoformat(),
            civil_utc_offset="+07:00",
        )
        cc["timezone"] = "+07:00"
        month["comparison_datetime"] = local.isoformat()
        month["elapsed_seconds_since_start"] = (
            actual
            - datetime.fromisoformat(
                month["start_term"]["datetime_with_offset"]
            ).astimezone(timezone.utc)
        ).total_seconds()
        month["elapsed_seconds_until_next"] = (
            datetime.fromisoformat(
                month["next_term"]["datetime_with_offset"]
            ).astimezone(timezone.utc)
            - actual
        ).total_seconds()
        for cast in [result["meihua"], cc["lunar_calendar"]["meihua"]]:
            for row in cast["rule_trace"]:
                if row["rule_id"] == "civil_clock_resolution":
                    row["inputs"]["timezone"] = "+07:00"
    elif name == "clock_UTC_naive":
        clock["instant_utc"] = (
            datetime.fromisoformat(clock["instant_utc"])
            .replace(tzinfo=None)
            .isoformat()
        )
        clock["input_components"]["nominal_instant_utc"] = clock["instant_utc"]
    elif name == "month_comparison_naive":
        month["comparison_datetime"] = (
            datetime.fromisoformat(month["comparison_datetime"])
            .replace(tzinfo=None)
            .isoformat()
        )
    elif name == "clock_version_changed":
        clock["version"] = "unreviewed"
    elif name == "zone_replaced_claim":
        clock["calendar_zone_replaced_by_offset"] = True
    elif name == "original_time_system_certified":
        clock["original_text_uniquely_prescribes_IANA_or_fold"] = True
    elif name == "month_elapsed_bool":
        month["elapsed_seconds_since_start"] = True
    elif name == "month_current_label_differs":
        ac["current_jieqi"] = "大暑"
    elif name == "UTC_Z_alias":
        clock["instant_utc"] = clock["instant_utc"].removesuffix("+00:00") + "Z"
        clock["input_components"]["nominal_instant_utc"] = clock["instant_utc"]
        ac["civil_instant_utc"] = clock["instant_utc"]
    elif name == "ISO_space_alias":
        clock["local_datetime"] = clock["local_datetime"].replace("T", " ")
        clock["input_components"]["nominal_civil_datetime"] = clock["local_datetime"]
        month["comparison_datetime"] = month["comparison_datetime"].replace("T", " ")
    else:
        raise AssertionError("Unknown frozen fault: " + name)
    clock_aliases(result, clock)
    return result
