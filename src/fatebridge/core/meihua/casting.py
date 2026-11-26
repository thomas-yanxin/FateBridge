"""Meihua casting (explicit methods + clock resolution + true solar time helper)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Literal, NamedTuple, TypedDict

from pydantic import JsonValue, TypeAdapter
from pydantic_core import PydanticCustomError
from typing_extensions import NotRequired

from fatebridge.core.meihua.relations import meihua_stage_relations
from fatebridge.core.meihua.texts import load_meihua_json
from fatebridge.utils.civil_clock import (
    format_utc_offset,
    resolve_civil_clock,
    utc_instant,
)
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.timezones import LocalClockError, timezone_rules_metadata


@lru_cache(maxsize=1)
def _casting_adapter() -> TypeAdapter[Any]:
    from fatebridge.core.requests.meihua import MeihuaCasting

    return TypeAdapter(MeihuaCasting)


BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
NUMBERS = {"乾": 1, "兑": 2, "离": 3, "震": 4, "巽": 5, "坎": 6, "艮": 7, "坤": 8}
CODENUMBERS = {
    "111": 1,
    "110": 2,
    "101": 3,
    "100": 4,
    "011": 5,
    "010": 6,
    "001": 7,
    "000": 8,
}
COMPONENTS = ("year", "month", "day", "hour", "minute", "second")

DATE_PATTERN = re.compile(
    r"(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{8}|[0-9]{4}-W[0-9]{2}(?:-[1-7])?|[0-9]{4}W[0-9]{2}[1-7]?)"
)
TIME_PATTERN = re.compile(
    r"([0-9]{2})(?:(:)([0-9]{2})(?::([0-9]{2}))?|([0-9]{2})([0-9]{2})?)?(?:[.,]([0-9]+))?"
)

UNSPECIFIED_MESSAGE = (
    "所选时区在该起卦钟时没有已定义的当地时间规则，不能按零偏移核验或计算。"
    "若已核实实际固定UTC偏移，请在analysis_timezone直接提供该明确偏移；"
    "analysis_utc_offset只核验地区规则，不能替代缺失的地区钟时定义。"
)


class MeihuaUnspecifiedClockError(ValueError):
    """The selected regional time type cannot verify a civil instant."""


class ClockInputReceipt(TypedDict):
    policy_id: str
    version: str
    rule_kind: str
    provenance: str
    supplied_components: list[str]
    omitted_components: list[str]
    calculation_defaults: dict[str, int]
    nominal_civil_datetime: str
    nominal_instant_utc: str
    status: Literal["nominal_defaults", "optional_components_supplied"]
    uncertainty_interval: None
    calendar_stability: Literal["not_assessed"]
    observed_precision_certified: Literal[False]
    original_text_uniquely_prescribes_this_precision: Literal[False]
    statement: str


class SecondInputEvidence(TypedDict):
    ruleset_id: str
    version: str
    rule_kind: str
    value: int
    seconds_enter_cast_seed: Literal[False]
    input_precision_certifies_accuracy: Literal[False]
    original_text_uniquely_prescribes_seconds: Literal[False]


class CivilClockEvidence(TypedDict):
    ruleset_id: str
    version: str
    rule_kind: str
    method: Literal[
        "explicit_offset_verified_against_timezone", "unambiguous_timezone_clock"
    ]
    timezone: str
    input_utc_offset: str | None
    resolved_utc_offset: str
    local_datetime: str
    instant_utc: str
    fold: int
    timezone_rules: dict[str, str]
    calendar_zone_replaced_by_offset: Literal[False]
    clock_label_precision: str
    input_second: NotRequired[SecondInputEvidence]
    original_text_uniquely_prescribes_IANA_or_fold: Literal[False]
    input_components: ClockInputReceipt


class ResolvedMeihuaClock(NamedTuple):
    civil_datetime: datetime
    evidence: CivilClockEvidence


def _clock_time_parts(text: str) -> tuple[int, int, int, int]:
    match = TIME_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError("Invalid clock or offset component spelling")
    hour, _, minute, second, basic_minute, basic_second, fraction = match.groups()
    h, m, s = (
        int(hour),
        int(minute or basic_minute or 0),
        int(second or basic_second or 0),
    )
    if h > 23 or m > 59 or s > 59:
        raise ValueError("Clock or offset component outside its declared range")
    fraction = fraction or ""
    if any(c != "0" for c in fraction[6:]):
        raise ValueError(
            "Nonzero precision beyond microseconds cannot be represented exactly"
        )
    return h, m, s, int(fraction[:6].ljust(6, "0"))


def _clock_time_and_offset(
    text: str,
) -> tuple[tuple[int, int, int, int], timezone | None]:
    marker = re.search(r"[+Z-]", text)
    if marker is None:
        return _clock_time_parts(text), None
    position = marker.start()
    clock = _clock_time_parts(text[:position])
    suffix = text[position:]
    if suffix == "Z":
        return clock, timezone.utc
    if suffix[0] not in "+-":
        raise ValueError("Invalid UTC offset suffix")
    h, m, s, micros = _clock_time_parts(suffix[1:])
    offset = timedelta(hours=h, minutes=m, seconds=s, microseconds=micros)
    return clock, timezone(-offset if suffix[0] == "-" else offset)


def parse_meihua_clock_label(value: str) -> datetime:
    """Decode ISO clock labels strictly without C-parser version drift."""
    if type(value) is not str or len(value) < 7:
        raise ValueError("Invalid Meihua clock label")
    try:
        sep = 10 if value[4] == "-" and value[5] != "W" else 8
        date_text = value[:sep]
        if DATE_PATTERN.fullmatch(date_text) is None:
            raise ValueError("Invalid Gregorian or ISO week date spelling")
        if "W" in date_text:
            clean = date_text.replace("-", "")
            d = date.fromisocalendar(
                int(clean[:4]), int(clean[5:7]), int(clean[7:8] or 1)
            )
        else:
            d = date.fromisoformat(
                f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:8]}"
                if "-" not in date_text
                else date_text
            )
        if sep == len(value):
            return datetime(d.year, d.month, d.day)
        time_text = value[sep + 1 :]
        if not time_text:
            raise ValueError("A datetime separator requires a time")
        (hour, minute, second, micros), offset = _clock_time_and_offset(time_text)
        return datetime(
            d.year, d.month, d.day, hour, minute, second, micros, tzinfo=offset
        )
    except (IndexError, OverflowError, TypeError, ValueError) as exc:
        raise ValueError(
            "Invalid or unsupported Meihua clock label: " + str(exc)
        ) from exc


def resolve_meihua_civil_clock(
    wall: datetime, zone: str, explicit_offset: str | None = None
) -> datetime:
    """Resolve civil clock instant under zone gap/fold rules."""
    try:
        return resolve_civil_clock(
            wall, zone, explicit_offset, timezone_field="analysis_timezone"
        )
    except LocalClockError as error:
        if error.code == "ambiguous_local_time":
            offsets = [
                format_utc_offset(offset)
                for fold in (0, 1)
                if (offset := error.moment.replace(fold=fold).utcoffset()) is not None
            ]
            raise ParameterError(
                "起卦钟时处于时区回拨造成的重复区间。请核实当时的 UTC 偏移并填写 analysis_utc_offset。",
                [
                    {
                        "path": "analysis_utc_offset",
                        "code": error.code,
                        "constraints": {"expected": offsets},
                    }
                ],
            ) from error
        raise ParameterError(
            "起卦钟时处于时区跳时区间。请核对当地日期、时刻和时区。",
            [{"path": "analysis_hour", "code": error.code}],
        ) from error
    except PydanticCustomError as error:
        if error.type == "unresolved_timezone_offset":
            raise MeihuaUnspecifiedClockError(UNSPECIFIED_MESSAGE) from error
        raise


def resolve_meihua_cast_datetime(
    moment: datetime,
    *,
    timezone_name: str | None = None,
    longitude: float | None = None,
    use_true_solar_time: bool = False,
) -> tuple[datetime, dict[str, Any]]:
    """Apply optional true solar time adjustment for meihua_time_cast."""
    if not use_true_solar_time:
        return moment, {
            "true_solar_time_applied": False,
            "corrected_datetime": moment.isoformat(),
            "total_correction_minutes": 0.0,
        }
    if longitude is None:
        raise ValueError("梅花真太阳时起卦需要提供经度 longitude。")
    from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
    from fatebridge.utils.solar_time import calculate_solar_time_adjustment

    tz_name = (
        timezone_name or getattr(moment.tzinfo, "key", None) or DEFAULT_BIRTH_TIMEZONE
    )
    adjustment = calculate_solar_time_adjustment(moment, tz_name, longitude)
    corrected = moment + timedelta(minutes=adjustment["total_correction_minutes"])
    return corrected, {
        "true_solar_time_applied": True,
        "corrected_datetime": corrected.isoformat(),
        "total_correction_minutes": adjustment["total_correction_minutes"],
        "longitude": longitude,
    }


def clock_components(
    minute: int | None,
    second: int | None,
    declared: list[str] | None,
) -> list[str]:
    """Return validated supplied clock component names."""
    inferred = [*COMPONENTS[:4]]
    if minute is not None:
        inferred.append("minute")
    if second is not None:
        inferred.append("second")
    if declared is None:
        return inferred
    if (
        type(declared) is not list
        or any(type(n) is not str or n not in COMPONENTS for n in declared)
        or declared != [n for n in COMPONENTS if n in declared]
        or declared[:4] != list(COMPONENTS[:4])
        or any(n in declared and n not in inferred for n in COMPONENTS[4:])
        or ("minute" not in declared and minute not in (None, 0))
        or ("second" not in declared and second not in (None, 0))
    ):
        raise ValueError("钟时输入分量记录与实际计算参数冲突")
    return list(declared)


def clock_input_receipt(
    local: datetime,
    instant_utc: str,
    supplied: list[str],
    provenance: str,
) -> ClockInputReceipt:
    """Build clock input receipt preserving nominal defaults metadata."""
    omitted = [component for component in COMPONENTS[4:] if component not in supplied]
    labels = {"minute": "分钟", "second": "秒数"}
    statement = (
        f"钟时计算参考为{local.isoformat()}；"
        + "、".join(f"{labels[n]}未提供，计算补00" for n in omitted)
        + "。"
        if omitted
        else "已提供分、秒分量。"
    )
    return {
        "policy_id": "meihua_clock_components_v1",
        "version": "1.0.0",
        "rule_kind": "software_convention",
        "provenance": provenance,
        "supplied_components": list(supplied),
        "omitted_components": omitted,
        "calculation_defaults": {n: 0 for n in omitted},
        "nominal_civil_datetime": local.isoformat(),
        "nominal_instant_utc": instant_utc,
        "status": "nominal_defaults" if omitted else "optional_components_supplied",
        "uncertainty_interval": None,
        "calendar_stability": "not_assessed",
        "observed_precision_certified": False,
        "original_text_uniquely_prescribes_this_precision": False,
        "statement": statement,
    }


def apply_clock_input_notice(
    interpretation: dict[str, Any], clock: CivilClockEvidence
) -> None:
    """Attach clock_input binding path to interpretation.evidence_scope."""
    receipt = clock["input_components"]
    interpretation["evidence_scope"]["clock_input"] = {
        "path": "meihua.calendar_policy.civil_clock_resolution.input_components",
        "status": receipt["status"],
        "calendar_basis": "nominal_reference_only",
        "observed_precision_certified": False,
        "calendar_stability": "not_assessed",
    }
    if receipt["omitted_components"]:
        for key in ("comprehensive_judgement", "traditional_judgement"):
            if interpretation.get(key):
                interpretation[key] = receipt["statement"] + " " + interpretation[key]


def resolve_meihua_clock(
    wall: datetime,
    timezone_name: str,
    explicit_offset: str | None,
    *,
    seconds_supplied: bool = False,
    minute_supplied: bool = True,
    component_provenance: str = "direct_datetime_components",
) -> ResolvedMeihuaClock:
    """Resolve a named-zone instant and build its CivilClockEvidence."""
    resolved_clock = resolve_meihua_civil_clock(wall, timezone_name, explicit_offset)
    utc_offset = resolved_clock.utcoffset()
    assert utc_offset is not None
    instant_utc = utc_instant(resolved_clock).isoformat()
    supplied_components = ["year", "month", "day", "hour"]
    if minute_supplied:
        supplied_components.append("minute")
    if seconds_supplied:
        supplied_components.append("second")
    evidence: CivilClockEvidence = {
        "ruleset_id": "meihua_civil_clock_v1",
        "version": "1.0.0",
        "rule_kind": "software_convention",
        "method": (
            "explicit_offset_verified_against_timezone"
            if explicit_offset is not None
            else "unambiguous_timezone_clock"
        ),
        "timezone": timezone_name,
        "input_utc_offset": explicit_offset,
        "resolved_utc_offset": format_utc_offset(utc_offset),
        "local_datetime": resolved_clock.isoformat(),
        "instant_utc": instant_utc,
        "fold": resolved_clock.fold,
        "timezone_rules": timezone_rules_metadata(timezone_name),
        "calendar_zone_replaced_by_offset": False,
        "clock_label_precision": (
            "supplied_civil_second; historical_offset_seconds_preserved"
            if seconds_supplied and minute_supplied
            else (
                "supplied_civil_minute; historical_offset_seconds_preserved"
                if minute_supplied
                else (
                    "hour_and_second_supplied; minute_00_calculation_default; historical_offset_seconds_preserved"
                    if seconds_supplied
                    else "supplied_civil_hour; minute_and_second_00_calculation_defaults; historical_offset_seconds_preserved"
                )
            )
        ),
        "original_text_uniquely_prescribes_IANA_or_fold": False,
        "input_components": clock_input_receipt(
            resolved_clock, instant_utc, supplied_components, component_provenance
        ),
    }
    if seconds_supplied:
        evidence["input_second"] = {
            "ruleset_id": "meihua_civil_second_input_v1",
            "version": "1.0.0",
            "rule_kind": "software_convention",
            "value": wall.second,
            "seconds_enter_cast_seed": False,
            "input_precision_certifies_accuracy": False,
            "original_text_uniquely_prescribes_seconds": False,
        }
    return ResolvedMeihuaClock(resolved_clock, evidence)


def _resolve_reported_observation(
    parameters: dict[str, Any],
) -> tuple[int, int, dict[str, Any]]:
    profile = load_meihua_json("observed-categories-nlc1925-v1.json")
    subject = profile["subjects"][parameters["subject_category"]]
    direction = profile["directions"][parameters["direction"]]
    role_label = {"from": "從", "toward": "往", "at": "在"}[
        parameters["direction_role"]
    ]
    basis = {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "subject": {
            "category": parameters["subject_category"],
            "source_label": subject["label"],
            "trigram": subject["trigram"],
            "number": subject["number"],
        },
        "direction": {
            "value": parameters["direction"],
            "role": parameters["direction_role"],
            "trigram": direction["trigram"],
            "number": direction["number"],
        },
        "summary": (
            f"端法依所报{subject['label']}、{role_label}{direction['label']}方，"
            f"取上{subject['trigram']}、下{direction['trigram']}。"
        ),
    }
    return subject["number"], direction["number"], basis


def _build_text_tone_basis(parameters: dict[str, Any]) -> dict[str, Any]:
    profile = load_meihua_json("tone-basis-v1.json")
    text, tones = parameters["text"], parameters["tones"]
    example = profile["selected_worked_example"]
    comparison_text = (
        text.translate(str.maketrans({"动": "動", "静": "靜"})) if text else None
    )
    differences: list[int] = []
    if comparison_text == example["text"]:
        differences = [
            i + 1
            for i, (actual, expected) in enumerate(zip(tones, example["tones"]))
            if actual != expected
        ]
        status = (
            "differs_from_selected_example_categories"
            if differences
            else "matches_selected_example_categories"
        )
    else:
        status = "text_not_supplied" if text is None else "different_text_not_compared"
    reference = parameters["tone_reference"]
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "reported_tones": list(tones),
        "reference": dict(reference) if reference is not None else None,
        "selected_example_comparison": {
            "status": status,
            "difference_positions": differences,
            "example_id": example["id"],
        },
    }


def cast_explicit_meihua(
    casting: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Cast an explicit Meihua hexagram across all 12 supported methods."""
    from fatebridge.core.divination import compose_meihua_hexagram

    parameters = _casting_adapter().validate_python(casting).model_dump(mode="json")
    method = parameters["method"]
    hour = (
        BRANCHES.index(parameters["hour_branch"]) + 1
        if "hour_branch" in parameters
        else 0
    )
    ignored: dict[str, Any] = {}
    alternate = None
    observation_basis = None
    if method == "lunar_time_added_count":
        year = BRANCHES.index(parameters["year_branch"]) + 1
        upper = (
            year
            + parameters["lunar_month"]
            + parameters["lunar_day"]
            + parameters["added_count"]
        )
        lower = upper + hour
        total = lower
    elif method == "sound_groups":
        upper, lower = parameters["first_count"], parameters["second_count"]
        raw_sum = upper + lower + hour
        reduced_sum = (upper % 8 or 8) + (lower % 8 or 8) + hour
        total = raw_sum if parameters["line_sum_basis"] == "raw_counts" else reduced_sum
        alternate = (
            reduced_sum if parameters["line_sum_basis"] == "raw_counts" else raw_sum
        ) % 6 or 6
    elif method == "object_count":
        upper, lower = parameters["count"], hour
        raw_sum = upper + hour
        reduced_sum = (upper % 8 or 8) + hour
        total = raw_sum if parameters["line_sum_basis"] == "raw_counts" else reduced_sum
        alternate = (
            reduced_sum if parameters["line_sum_basis"] == "raw_counts" else raw_sum
        ) % 6 or 6
    elif method == "observed_categories":
        upper, lower, observation_basis = _resolve_reported_observation(parameters)
        total = upper + lower + hour
    elif method == "observed_trigrams":
        upper = NUMBERS[parameters["upper_trigram"]]
        lower = NUMBERS[parameters["lower_trigram"]]
        total = upper + lower + hour
    elif method == "length_zhang_chi":
        upper, lower = parameters["zhang"], parameters["chi"]
        total = upper + lower
        if parameters["cun"] is not None:
            ignored["cun"] = parameters["cun"]
    elif method == "length_chi_cun":
        upper, lower = parameters["chi"], parameters["cun"]
        total = upper + lower + hour
        if parameters["fen"] is not None:
            ignored["fen"] = parameters["fen"]
    elif method in {"text_tones", "text_strokes"}:
        counts = parameters["tones" if method == "text_tones" else "strokes"]
        split = len(counts) // 2
        upper, lower = sum(counts[:split]), sum(counts[split:])
        total = upper + lower
    elif method == "single_character_strokes":
        upper, lower = parameters["left_strokes"], parameters["right_strokes"]
        total = parameters["total_strokes"]
    elif method == "text_count":
        upper = parameters["character_count"] // 2
        lower = parameters["character_count"] - upper
        raw_sum = upper + lower
        reduced_sum = (upper % 8 or 8) + (lower % 8 or 8)
        total = raw_sum if parameters["line_sum_basis"] == "raw_counts" else reduced_sum
        alternate = (
            reduced_sum if parameters["line_sum_basis"] == "raw_counts" else raw_sum
        ) % 6 or 6
    else:
        code = parameters["hexagram_code"]
        upper, lower = CODENUMBERS[code[3:]], CODENUMBERS[code[:3]]
        total = parameters["moving_line"]

    moving_line = total % 6 or 6
    seed: dict[str, Any] = {
        "casting_method": method,
        "upper_number": upper % 8 or 8,
        "lower_number": lower % 8 or 8,
        "moving_line": moving_line,
        "parameters": parameters,
        "ignored_components": ignored,
    }
    if "hour_branch" in parameters:
        seed["hour_branch"] = parameters["hour_branch"]
    if observation_basis is not None:
        seed["observation_basis"] = observation_basis
    if method == "text_tones":
        seed["text_tone_basis"] = _build_text_tone_basis(parameters)
    if method == "text_count":
        facsimile = parameters["text_basis"] == "nlc1925_selected_span"
        seed["text_count_basis"] = {
            "text_basis": parameters["text_basis"],
            "selected_wording": "百餘字" if facsimile else "百字",
            "character_count": parameters["character_count"],
            "range_status": (
                "software_extension_exact_textual_extent_unadjudicated"
                if parameters["character_count"] > 100
                else "within_fixed_transcription_working_range"
            ),
        }
    if method != "existing":
        seed.update(
            {"raw_upper_number": upper, "raw_lower_number": lower, "line_sum": total}
        )
    if alternate is not None:
        seed.update(
            {
                "line_sum_basis": parameters["line_sum_basis"],
                "alternate_moving_line": alternate,
                "count_boundary_status": (
                    "convention_changes_result"
                    if alternate != moving_line
                    else "conventions_agree_for_this_input"
                ),
            }
        )
    trace = [
        {
            "rule_id": method,
            "operation": f"cast_{method}",
            "inputs": parameters,
            "result": {
                "upper_number": seed["upper_number"],
                "lower_number": seed["lower_number"],
                "moving_line": moving_line,
            },
        }
    ]
    variants: list[dict[str, Any]] = []
    if alternate is not None and alternate != moving_line:
        for basis, line in [
            (parameters["line_sum_basis"], moving_line),
            (
                (
                    "trigram_numbers"
                    if parameters["line_sum_basis"] == "raw_counts"
                    else "raw_counts"
                ),
                alternate,
            ),
        ]:
            variant = compose_meihua_hexagram(
                upper_number=seed["upper_number"],
                lower_number=seed["lower_number"],
                moving_line=line,
            )
            variants.append(
                {
                    "line_sum_basis": basis,
                    "selected": line == moving_line,
                    "moving_line": line,
                    "base_code": variant["base_hexagram"]["binary_code"],
                    "changed_code": variant["changed_hexagram"]["binary_code"],
                    "mutual_code": variant["mutual_hexagram"]["binary_code"],
                    "base_hexagram": variant["base_hexagram"],
                    "changed_hexagram": variant["changed_hexagram"],
                    "mutual_hexagram": variant["mutual_hexagram"],
                    "body_trigram": variant["body_trigram"],
                    "use_trigram": variant["use_trigram"],
                    "body": variant["body_trigram"]["name"],
                    "use": variant["use_trigram"]["name"],
                    "moving_palace": variant["moving_palace"],
                    "body_use_relation": variant["body_use_relation"],
                    "stage_relations": meihua_stage_relations(
                        variant, fact_prefix=f"meihua.counting_variants.{len(variants)}"
                    ),
                }
            )
    return {
        "method": "meihua_" + method,
        "seed": seed,
        "counting_variants": variants,
        **compose_meihua_hexagram(
            upper_number=seed["upper_number"],
            lower_number=seed["lower_number"],
            moving_line=moving_line,
            label="梅花显式卦",
        ),
    }, trace
