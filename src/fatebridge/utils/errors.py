"""Caller-facing error envelopes and runtime diagnostics."""

from __future__ import annotations

import difflib
import logging
import types
from collections.abc import Collection, Iterable, Mapping, Sequence
from functools import wraps
from traceback import walk_tb
from typing import Annotated, Any, Callable, ParamSpec, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails, PydanticCustomError

logger = logging.getLogger(__name__)
P = ParamSpec("P")

DEPENDENCY_ERROR_CODE = "dependency_missing"
INTERNAL_ERROR_CODE = "internal_error"
TIMEOUT_ERROR_CODE = "timeout"
VALIDATION_ERROR_CODE = "validation_error"
UNRESOLVED_OFFSET_MESSAGE = (
    "unresolved local time：该日期的时区规则标记当地UT偏移未知，不能按零偏移计算；"
    "请提供已核实的出生钟时偏移。"
)


class DomainSourceError(Exception):
    """Base for source/configuration errors that callers cannot fix via birth inputs."""

    reason: str

    def as_result(self) -> dict[str, Any]:
        raise NotImplementedError


class NumerologySourceError(DomainSourceError, RuntimeError):
    """A source/configuration inconsistency cannot be fixed by changing a birth input."""

    MESSAGES = {
        "invalid_month_source_data": "河洛卦月来源数据未能通过一致性核对。",
        "invalid_pillar_link_source_data": "河洛卷七起月起时来源数据未能通过一致性核对。",
        "invalid_heluo_header_collation": "河洛爻辞校勘来源缺失或未能通过一致性核对。",
        "invalid_heluo_commentary_collation": "河洛注文校勘来源缺失或未能通过一致性核对。",
        "invalid_heluo_poem_collation": "河洛卷三诗诀校勘来源缺失或未能通过一致性核对。",
        "invalid_canping_schedule_collation": "参评配运原句或版本出处未能通过来源一致性核对。",
        "invalid_canping_text_source": "参评文字来源缺失或无法解析，需维护者核查。",
        "invalid_canping_text_collation": "参评主本原文或校勘身份与已核修订不符，需维护者核查。",
        "invalid_numerology_knowledge_sources": "河洛／参评知识来源目录或原文身份与所核修订不符，需维护者核查。",
        "runtime_canping_schedule_profile_conflict": "参评配运来源回执与实际方法不一致，需维护者核查。",
        "runtime_canping_schedule_binding_conflict": "参评配运释文、来源角色或时钟回执不一致，需维护者核查。",
        "invalid_heluo_clock_source": "河洛卷一百刻与寄时原句来源未能通过一致性核对。",
        "runtime_heluo_jiehou_context_conflict": "内部节气名、象限或时刻证据不一致，需维护者核查节候上下文。",
        "runtime_heluo_year_context_conflict": "内部岁运年标签与出生年柱不一致，需维护者核查计算上下文。",
        "runtime_heluo_yuanqi_context_conflict": "内部年命元气映射或同阶段卦体不一致，需维护者核查计算上下文。",
        "runtime_heluo_solar_context_conflict": "河洛所用节气、至点或四立来源与当前历法上下文不一致，需维护者核查。",
        "runtime_numerology_clock_input_conflict": "二数出生钟时分量回执与原始请求或实际计算不一致，需维护者核查。",
        "runtime_pillar_link_conflict": "内部四柱与所核起月起时规则不一致，需维护者核查计算来源。",
        "runtime_month_assignment_conflict": "卦属月计算表与已核原页冲突。",
        "runtime_assignment_conflict": "河洛纳甲实际正纳／借用与所核原页位置冲突。",
        "hexagram_mismatch": "河洛纳甲原页卦名与本次六爻不一致。",
    }

    def __init__(self, reason: str) -> None:
        if reason not in self.MESSAGES:
            raise RuntimeError("Unknown numerology source consistency reason")
        self.reason = reason
        super().__init__(self.MESSAGES[reason])

    def as_result(self) -> dict[str, Any]:
        return {
            "error": str(self),
            "error_code": "numerology_source_inconsistent",
            "status_code": 503,
            "retryable": False,
            "issues": [{"path": "runtime.numerology_sources", "code": self.reason}],
        }


class EphemerisCalculationError(RuntimeError):
    """A loaded native ephemeris calculation failed without a verified cause."""


class EphemerisSourceError(DomainSourceError, ValueError):
    """Safe, enumerated data-consistency failure; no paths or personal input."""

    MESSAGES = {
        "solar_native_unavailable": "Selected native solar model could not solve the requested crossing; no linear approximation is returned",
        "solar_native_context_unavailable": "Native solar refinement could not verify its actual compressed-file source contexts",
        "solar_term_source_unverified": "Solar-term crossing lacks a verified current model and source record; no approximate boundary is returned",
        "earth_attitude_model_unavailable": "Native nutation and obliquity required for Earth attitude are unavailable",
        "horizon_direction_model_unavailable": "Eastern horizon direction requires a valid coherent native house-angle model",
        "house_projection_precision_unavailable": "House-plane direction or its half-open house could not be resolved at the available working precision",
        "horizon_direction_precision_unavailable": "Eastern horizon endpoint direction could not be resolved at the available working precision",
        "swiss_dependency_unavailable": "A SWIEPH physical observation lacks complete observed planet and Moon file coverage; its top-level flag cannot exclude an analytical Moon dependency",
        "ren_solar_term_point_inconsistent": "Consumed Liu Ren or Jin Kou solar-term numerical TT evidence does not match its bracket or civil instant",
        "solar_de440_invalid": "Packaged DE440 solar coefficients are missing, corrupt, or inconsistent with their declared source",
        "solar_analytic_invalid": "Packaged analytic solar or frame coefficients are missing, corrupt, or differ from the reviewed ERFA source",
        "solar_swiss_files_required": "Explicit Swiss solar mode requires a solved crossing from Swiss planet and Moon files; analytical or linear fallback is not allowed",
        "solar_swiss_range": "Explicit Swiss solar mode does not cover the requested derived solar boundary; no shortened horizon or substitute model is returned",
        "solar_de440_range": "Packaged DE440 solar coefficients do not cover the requested TDB epoch including light time",
        "solar_spk_unavailable": "Selected solar SPK file is unavailable",
        "solar_spk_invalid": "Selected solar SPK requires valid type2 Earth, Earth-Moon barycenter and Sun segments in J2000 frame 1",
        "solar_spk_range": "Selected solar SPK does not cover the required TDB interval including solar light time",
        "solar_spk_changed": "Selected solar SPK changed during calculation",
        "solar_vsop2013_unavailable": "Selected VSOP2013 model manifest or library is unavailable",
        "solar_vsop2013_invalid": "Selected VSOP2013 bytes, initialized ABI, source profile or platform do not match the build receipt",
        "solar_vsop2013_changed": "Selected VSOP2013 manifest or library changed during calculation",
        "solar_vsop2013_range": "Selected VSOP2013 model is outside its declared working TT interval",
        "solar_vsop2013_calculation": "VSOP2013 Sun calculation returned invalid coordinates, source state or physical options",
        "solar_aa1996_unavailable": "Selected AA1996 model manifest or library is unavailable",
        "solar_aa1996_invalid": "Selected AA1996 model bytes, ABI, source profile or platform do not match the build receipt",
        "solar_aa1996_changed": "Selected AA1996 manifest or library changed during calculation",
        "solar_aa1996_range": "Selected AA1996 model is outside its declared working TT interval",
        "solar_aa1996_calculation": "AA1996 Sun calculation returned non-finite values or unexpected physical options",
        "birth_clock_source_mismatch": "Birth-clock conversion and physical calculation use inconsistent Sun sources or time-scale mappings; resolve the original clock under one coherent configuration",
        "timezone_rules_unavailable": "Declared named timezone data could not be read",
        "timezone_rules_invalid": "Declared named timezone data is not a valid TZif rule set",
        "human_design_reference_invalid": "Human Design reference data is not a valid unambiguous JSON object",
        "event_clock_source_mismatch": "Event-clock conversion and native chart use inconsistent observed Sun sources or physical time axes",
        "lunar_motion_position_mismatch": "Lunar motion correction could not reproduce the requested position frame and physical source",
        "lunar_motion_center_not_reproduced": "Lunar observer sampling could not reproduce the original center states and flags exactly",
        "sidereal_origin_not_reproduced": "Traditional sidereal origin could not be reproduced exactly after its derivative inputs were read",
        "observer_source_window_incoherent": "A geometric observer sample violates its declared epoch, coordinate contract or unchanged center-file window",
        "lunar_source_window_incoherent": "Selected lunar source intervals do not cover the complete reception light path",
        "position_motion_not_converged": "Complete apparent-position motion failed its fixed step-convergence line",
        "compressed_endpoint_unresolved": "Compressed ephemeris endpoint could not be recalculated inside a consistent adjacent file context",
        "dependency_source_window_incoherent": "Physical reception and retarded dependency do not share an unchanged observed file context",
        "compressed_endpoint_unverified": "Compressed ephemeris endpoint selection is not verified for the loaded native version",
        "coordinate_contract_changed": "Native ephemeris returned a different coordinate frame or correction convention than requested",
        "coordinate_values_unavailable": "Ephemeris coordinates are missing, nonfinite, or outside their valid domain",
        "opaque_solar_barycentric_unavailable": "Opaque-Sun apparent positions could not obtain their native barycentric states",
        "opaque_solar_requires_barycentric_files": "Opaque-Sun apparent positions require actual barycentric file states; analytical fallback is not accepted",
        "light_cone_not_bracketed": "Source light cone could not be bracketed at adjacent representable epochs",
        "coordinate_motion_unavailable": "Native ephemeris did not provide the requested finite longitude motion",
        "jpl_filename_invalid": "Strict JPL kernel must be a short basename in the configured ephemeris search path",
        "jpl_file_unavailable": "Selected strict JPL kernel could not be opened",
        "jpl_kernel_invalid": "Selected strict JPL kernel is not a complete supported DE441 direct-access file",
        "jpl_kinematics_invalid": "Selected DE441 source record or analytic kinematic inputs are invalid",
        "de441_archive_missing": "Required DE441 coefficient chunk is missing. Set FATEBRIDGE_DE441_DIR to the matching release's coefficient archive directory",
        "jpl_kinematics_outside_source": "Requested analytic kinematics are outside the selected DE441 source interval",
        "jpl_kinematics_frame_mismatch": "Raw DE441 position and velocity do not reproduce the native fixed observer frame",
        "jpl_mixed_request": "Strict JPL mode cannot mix an explicit analytical ephemeris request",
        "jpl_swiss_file_requirement_conflict": "Explicit JPL selection cannot satisfy require_swiss_files=true; that option requires Swiss compressed data files",
        "jpl_native_fallback": "Native calculation downgraded from the selected strict JPL kernel",
        "jpl_native_failed": "Native calculation failed with the selected strict JPL kernel",
        "invalid_range": "Invalid physical ephemeris file range",
        "slot_changed": "Physical ephemeris file slot changed",
        "unavailable_during": "Physical ephemeris file became unavailable during factor calculation",
        "changed_during": "Physical ephemeris file changed during factor calculation",
        "model_changed": "Physical ephemeris model changed across calculation points; install complete ephemeris segments for the declared interval and reload the runtime",
        "edition_changed": "Physical ephemeris DE header editions changed across birth-time samples",
        "changed_across": "Physical ephemeris file changed across birth-time samples",
        "solar_configuration_changed": "Ephemeris configuration changed during the Sun calculation batch",
        "solar_natal_source_mismatch": "Natal Sun source differs between the native chart and the direction calculation",
        "mixed_pair_sample_epoch_mismatch": "Native and solar birth-time samples do not share the same effective instant and TT epoch; rebuild a coherent sample set",
        "comparative_geometry_inputs": "Comparative geometry requires a coherent native factor set and the complete same-run birth-time grid, including the matching nominal TT epoch",
        "source_pattern_inputs": "Source-pattern assessment requires finite native factors and a valid reference-angle definition",
        "day_meridian_inputs": "Day-meridian inputs must match the complete same-run native grid, reference definitions, UTC/TT epochs and actual Sun observation roles",
        "physical_configuration_changed": "Ephemeris configuration changed during physical chart calculation",
        "coordinate_model_changed": "Physical ephemeris model differs between ecliptic and equatorial coordinates",
        "nominal_source_mismatch": "Physical ephemeris source differs between the nominal chart and recalculated same-epoch factors",
        "fictitious_identity": "Fictitious element slot does not identify the requested Hamburg factor; cannot label an unrelated orbit as a Hamburg factor",
    }

    def __init__(self, reason: str) -> None:
        if reason not in self.MESSAGES:
            raise ValueError("Unknown physical-ephemeris consistency reason")
        self.reason = reason
        super().__init__(self.MESSAGES[reason])

    def as_result(self) -> dict[str, Any]:
        return {
            "error": str(self),
            "error_code": "ephemeris_source_inconsistent",
            "status_code": 503,
            "retryable": False,
            "issues": [{"path": "runtime.ephemeris_data", "code": self.reason}],
        }


class ValidationIssue(BaseModel):
    """A field or domain rule the caller can use to diagnose a failure."""

    path: str
    code: str
    message: str | None = None
    constraints: dict[str, object] | None = None


class ErrorEnvelope(BaseModel):
    error: Any
    error_code: str
    retryable: bool
    issues: list[ValidationIssue] | None = None


class ParameterError(ValueError):
    """A caller-correctable parameter failure with public field paths."""

    def __init__(
        self, message: str, issues: list[dict[str, object]], *, status_code: int = 422
    ) -> None:
        super().__init__(message)
        self.issues = issues
        self.status_code = status_code

    def as_result(self) -> dict[str, Any]:
        return {
            "error": str(self),
            "error_code": VALIDATION_ERROR_CODE,
            "status_code": self.status_code,
            "retryable": False,
            "issues": self.issues,
        }


def unknown_tool_issue(
    tool: str,
    candidates: Iterable[str],
    *,
    path: str = "tool",
) -> dict[str, object]:
    """Build the shared unknown-tool diagnostic issue with fuzzy suggestions."""
    suggestions = difflib.get_close_matches(
        tool, sorted(set(candidates)), n=5, cutoff=0.4
    )
    issue: dict[str, object] = {"path": path, "code": "unknown_tool"}
    if suggestions:
        issue["constraints"] = {"suggestions": suggestions}
    return issue


def unknown_tool_error(
    tool: str,
    candidates: Iterable[str],
    *,
    path: str = "tool",
) -> ParameterError:
    """Build the shared 404 ParameterError for unknown tool names."""
    return ParameterError(
        f"未知工具: {tool}",
        [unknown_tool_issue(tool, candidates, path=path)],
        status_code=404,
    )


_EXTRA_FIELD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "params": ("arguments", "defaults", "context"),
    "input": ("arguments", "context", "subjects"),
    "payload": ("arguments", "context", "calls"),
    "args": ("arguments",),
    "kwargs": ("arguments",),
    "birth_place_name": ("birth_place",),
    "place_name": ("place", "analysis_place", "birth_place"),
    "tz": ("timezone", "analysis_timezone", "birth_timezone", "timezone_name"),
    "lon": ("longitude", "analysis_longitude", "birth_longitude"),
    "lng": ("longitude", "analysis_longitude", "birth_longitude"),
    "lat": ("latitude", "analysis_latitude", "birth_latitude"),
}


def _expand_cursor_types(annotation: object) -> list[object]:
    """Expand Annotated and Union wrappers into concrete candidate types."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _expand_cursor_types(get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        expanded: list[object] = []
        for arg in get_args(annotation):
            if arg is not type(None):
                expanded.extend(_expand_cursor_types(arg))
        return expanded
    return [annotation]


def _resolve_model_fields_at_loc(
    root_model: type[BaseModel] | None,
    loc: tuple[str | int, ...],
) -> set[str] | None:
    """Walk Pydantic error location path to recover allowed fields of the failing container model."""
    if root_model is None:
        return None
    cursor_types: list[object] = [root_model]
    for part in loc[:-1]:
        next_types: list[object] = []
        expanded_cursor: list[object] = []
        for candidate in cursor_types:
            expanded_cursor.extend(_expand_cursor_types(candidate))
        for candidate in expanded_cursor:
            if isinstance(part, int):
                origin = get_origin(candidate)
                if origin in (list, Sequence, set, frozenset):
                    args = get_args(candidate)
                    if args:
                        next_types.append(args[0])
                elif origin is tuple:
                    args = get_args(candidate)
                    if len(args) == 2 and args[1] is Ellipsis:
                        next_types.append(args[0])
                    elif 0 <= part < len(args):
                        next_types.append(args[part])
                continue
            part_str = str(part)
            if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                field_info = candidate.model_fields.get(part_str)
                if field_info is None:
                    for candidate_field in candidate.model_fields.values():
                        if candidate_field.alias == part_str:
                            field_info = candidate_field
                            break
                if field_info is not None and field_info.annotation is not None:
                    next_types.append(field_info.annotation)
                continue
            origin = get_origin(candidate)
            if origin in (dict, Mapping):
                args = get_args(candidate)
                if len(args) == 2:
                    next_types.append(args[1])
        if not next_types:
            return None
        cursor_types = next_types

    fields: set[str] = set()
    for candidate in cursor_types:
        for concrete in _expand_cursor_types(candidate):
            if isinstance(concrete, type) and issubclass(concrete, BaseModel):
                fields.update(concrete.model_fields.keys())
    return fields or None


def validation_error_result(
    error: ValidationError,
    *,
    allowed_fields: Collection[str] | None = None,
    root_model: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Return validator feedback to the caller without attaching the input body."""
    return validation_issues_result(
        error.errors(include_input=False, include_url=False),
        allowed_fields=allowed_fields,
        root_model=root_model,
    )


def validation_issues_result(
    entries: Sequence[ErrorDetails],
    *,
    allowed_fields: Collection[str] | None = None,
    root_model: type[BaseModel] | None = None,
) -> dict[str, Any]:
    # note (Pydantic): Keep typed native source faults carried in ctx.error.
    if not any(item["type"] == "consultation_restricted" for item in entries):
        for item in entries:
            cause = (item.get("ctx") or {}).get("error")
            if isinstance(cause, EphemerisSourceError):
                return cause.as_result()
    issues: list[dict[str, object]] = []
    is_restricted = False
    message = "请求参数无效"
    for item in entries:
        loc = item["loc"]
        context = item.get("ctx") or {}
        code = item["type"]
        path = ".".join(str(part) for part in loc)
        cause = context.get("error")
        if isinstance(cause, ParameterError):
            issues.extend(
                {
                    "message": str(cause),
                    **issue,
                    "path": f"{path}.{issue['path']}" if path else issue["path"],
                }
                for issue in cause.issues
            )
            continue
        constraints: dict[str, object] = {
            key: context[key]
            for key in (
                "ge",
                "gt",
                "le",
                "lt",
                "min_length",
                "max_length",
                "expected",
                "pattern",
                "required_with",
                "allowed",
                "suggestions",
                "available",
            )
            if key in context
        }
        if code == "extra_forbidden" and loc:
            target_fields = _resolve_model_fields_at_loc(root_model, tuple(loc))
            if target_fields is None and allowed_fields and len(loc) == 1:
                target_fields = set(allowed_fields)
            if target_fields:
                sorted_fields = sorted(target_fields)
                constraints["allowed_fields"] = sorted_fields
                if "suggestions" not in constraints:
                    unknown_name = str(loc[-1])
                    synonym_hits = [
                        candidate
                        for candidate in _EXTRA_FIELD_SYNONYMS.get(
                            unknown_name.lower(), ()
                        )
                        if candidate in target_fields
                    ]
                    fuzzy_hits = difflib.get_close_matches(
                        unknown_name, sorted_fields, n=5, cutoff=0.5
                    )
                    suggestions = list(dict.fromkeys([*synonym_hits, *fuzzy_hits]))[:5]
                    if suggestions:
                        constraints["suggestions"] = suggestions
        if field := context.get("path"):
            path = f"{path}.{field}" if path else field
        issue_message = item["msg"]
        if code == "consultation_restricted":
            is_restricted = True
            constraints = {"policy": context["policy"]}
        elif code == "json_invalid":
            path = "request"
            if loc:
                constraints["position"] = loc[0]
            if cause:
                issue_message = f"{issue_message}: {cause}"
        elif code == "value_error" and isinstance(cause, ValueError):
            issue_message = str(cause) or issue_message
        if message == "请求参数无效" and code in {
            "unsupported_house_system",
            "invalid_house_system",
            "invalid_house_code",
            "unresolved_timezone_offset",
        }:
            message = issue_message
        issue: dict[str, object] = {
            "path": path or "request",
            "code": code,
            "message": issue_message,
        }
        if constraints:
            issue["constraints"] = constraints
        issues.append(issue)
    return {
        "error": "此请求超出允许的咨询范围" if is_restricted else message,
        "error_code": (
            "consultation_restricted" if is_restricted else VALIDATION_ERROR_CODE
        ),
        "status_code": 422,
        "retryable": False,
        "issues": issues,
    }


def handle_calculation_error(
    error: Exception,
    operation: str,
    *,
    allowed_fields: Collection[str] | None = None,
    root_model: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Return caller diagnostics and log only exception identity and stack locations."""
    if isinstance(error, ValidationError):
        return validation_error_result(
            error, allowed_fields=allowed_fields, root_model=root_model
        )
    if isinstance(error, ParameterError):
        return error.as_result()
    if isinstance(error, DomainSourceError):
        logger.error(f"{operation} failed ({type(error).__name__}: {error.reason})")
        return error.as_result()

    if (
        isinstance(error, PydanticCustomError)
        and error.type == "unresolved_timezone_offset"
    ):
        return {
            "error": UNRESOLVED_OFFSET_MESSAGE,
            "error_code": VALIDATION_ERROR_CODE,
            "status_code": 422,
            "retryable": False,
            "issues": [{"path": "request", "code": error.type}],
        }

    if isinstance(error, ValueError):
        return {
            "error": str(error).strip() or f"{operation}输入无效",
            "error_code": VALIDATION_ERROR_CODE,
            "status_code": 400,
            "retryable": False,
        }

    cause = error.__cause__ or error
    frames = " -> ".join(
        f"{frame.f_globals.get('__name__')}.{frame.f_code.co_name}:{line}"
        for frame, line in walk_tb(cause.__traceback__)
    )
    logger.error(f"{operation} failed ({type(cause).__name__}) {frames}")
    if isinstance(error, EphemerisCalculationError):
        message, code, status, retryable = (
            "原生星历计算失败，请检查运行环境",
            "ephemeris_calculation_failed",
            503,
            False,
        )
    elif isinstance(error, ModuleNotFoundError):
        message, code, status, retryable = (
            "所需依赖缺失，请检查运行环境",
            DEPENDENCY_ERROR_CODE,
            503,
            False,
        )
    elif isinstance(error, TimeoutError):
        message, code, status, retryable = (
            "处理超时，请稍后重试",
            TIMEOUT_ERROR_CODE,
            504,
            True,
        )
    else:
        message, code, status, retryable = (
            "暂时不可用，请稍后重试",
            INTERNAL_ERROR_CODE,
            500,
            True,
        )
    return {
        "error": f"{operation}{message}",
        "error_code": code,
        "status_code": status,
        "retryable": retryable,
    }


def calculation_guard(
    operation: str,
) -> Callable[[Callable[P, dict[str, Any]]], Callable[P, dict[str, Any]]]:
    """Return the shared error envelope for direct service callers."""

    def decorator(
        func: Callable[P, dict[str, Any]],
    ) -> Callable[P, dict[str, Any]]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
            try:
                return func(*args, **kwargs)
            except (
                Exception
            ) as exc:  # noqa: BLE001 - preserve the public error envelope
                return handle_calculation_error(exc, operation)

        return wrapper

    return decorator


def error_response_payload(data: dict[str, Any], operation: str) -> dict[str, Any]:
    """The shared JSON error envelope used by all transports."""
    return {
        "error": data["error"],
        "error_code": data.get("error_code", INTERNAL_ERROR_CODE),
        "status_code": data.get("status_code", 500),
        "retryable": data.get("retryable", False),
        "operation": operation,
        **({"issues": data["issues"]} if "issues" in data else {}),
    }
