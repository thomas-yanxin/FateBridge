"""Standardised calculation error envelope + guard decorator.

Extracted verbatim from utils/helpers.py (god-file split). Pure error
formatting/control-flow — no numerical computation.
"""

import logging
from builtins import TimeoutError as BuiltinTimeoutError
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, ParamSpec

from pydantic import BaseModel
from pydantic_core import PydanticCustomError

logger = logging.getLogger(__name__)
_P = ParamSpec("_P")

DEPENDENCY_ERROR_CODE = "dependency_missing"
INTERNAL_ERROR_CODE = "internal_error"
TIMEOUT_ERROR_CODE = "timeout"
VALIDATION_ERROR_CODE = "validation_error"
UNRESOLVED_OFFSET_MESSAGE = (
    "unresolved local time：该日期的时区规则标记当地UT偏移未知，不能按零偏移计算；"
    "请提供已核实的出生钟时偏移。"
)


class NumerologySourceError(RuntimeError):
    """A source/configuration inconsistency cannot be fixed by changing a birth input."""

    MESSAGES = {
        "solar_native_context_unavailable": "Native solar refinement could not verify its actual compressed-file source contexts",
        "invalid_source_data": "河洛纳甲来源数据未能通过一致性核对。",
        "invalid_month_source_data": "河洛卦月来源数据未能通过一致性核对。",
        "invalid_line_condition_source_data": "河洛爻位原句来源数据未能通过一致性核对。",
        "invalid_body_structure_source_data": "河洛卦体结构原例来源数据未能通过一致性核对。",
        "invalid_pillar_link_source_data": "河洛卷七起月起时来源数据未能通过一致性核对。",
        "invalid_heluo_header_collation": "河洛爻辞校勘来源缺失或未能通过一致性核对。",
        "invalid_heluo_commentary_collation": "河洛注文校勘来源缺失或未能通过一致性核对。",
        "invalid_heluo_poem_collation": "河洛卷三诗诀校勘来源缺失或未能通过一致性核对。",
        "invalid_canping_schedule_collation": "参评配运原句或版本出处未能通过来源一致性核对。",
        "invalid_canping_text_source": "参评文字来源缺失或无法解析，需维护者核查。",
        "invalid_canping_text_collation": "参评主本原文或校勘身份与已核修订不符，需维护者核查。",
        "invalid_canping_witness_collation": "参评对读原文或独立书影身份与所存修订不符，需维护者核查。",
        "invalid_numerology_knowledge_sources": "河洛／参评知识来源目录或原文身份与所核修订不符，需维护者核查。",
        "runtime_numerology_knowledge_binding_conflict": "河洛／参评知识回执与原始查询或所核来源不一致，需维护者核查。",
        "runtime_canping_schedule_profile_conflict": "参评配运来源回执与实际方法不一致，需维护者核查。",
        "runtime_canping_schedule_binding_conflict": "参评配运释文、来源角色或时钟回执不一致，需维护者核查。",
        "invalid_heluo_clock_source": "河洛卷一百刻与寄时原句来源未能通过一致性核对。",
        "invalid_heluo_jiehou_source": "河洛卷一节卦与候卦原表未能通过来源一致性核对。",
        "runtime_heluo_jiehou_context_conflict": "内部节气名、象限或时刻证据不一致，需维护者核查节候上下文。",
        "runtime_heluo_year_context_conflict": "内部岁运年标签与出生年柱不一致，需维护者核查计算上下文。",
        "invalid_heluo_opposition_source": "河洛元气相反原句与映射未能通过来源一致性核对。",
        "runtime_heluo_yuanqi_context_conflict": "内部年命元气映射或同阶段卦体不一致，需维护者核查计算上下文。",
        "runtime_heluo_solar_context_conflict": "河洛所用节气、至点或四立来源与当前历法上下文不一致，需维护者核查。",
        "runtime_numerology_solar_source_conflict": "二数实际节气模型与来源索引不一致，需维护者核查。",
        "runtime_numerology_clock_input_conflict": "二数出生钟时分量回执与原始请求或实际计算不一致，需维护者核查。",
        "runtime_pillar_link_conflict": "内部四柱与所核起月起时规则不一致，需维护者核查计算来源。",
        "runtime_month_assignment_conflict": "卦属月计算表与已核原页冲突。",
        "runtime_assignment_conflict": "河洛纳甲实际正纳／借用与所核原页位置冲突。",
        "hexagram_mismatch": "河洛纳甲原页卦名与本次六爻不一致。",
    }

    def __init__(self, reason: str) -> None:
        if reason not in self.MESSAGES:
            # Unregistered engine reasons cannot be corrected with birth data.
            raise RuntimeError("Unknown numerology source consistency reason")
        self.reason = reason
        super().__init__(self.MESSAGES[reason])

    def as_result(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "error_code": "numerology_source_inconsistent",
            "status_code": 503,
            "retryable": False,
            "issues": [{"path": "runtime.numerology_sources", "code": self.reason}],
        }


class FengshuiCalculationError(RuntimeError):
    """Internal plate contradictions cannot be resolved by changing user facts."""

    MESSAGES = {
        "natal_identity_mismatch": "玄空计算盘与本次选定的宅运或山向不一致。",
        "natal_plate_inconsistent": "玄空计算盘的九宫数字、排列或逐宫表示不一致。",
        "natal_trace_inconsistent": "玄空计算盘的种子、中心星或顺逆计算记录不一致。",
        "natal_structure_inconsistent": "玄空派生数式、结构标签或合取结论与原盘数字不一致。",
        "natal_mutual_geometry_inconsistent": "玄空先后天互用图位、来源或候选星数不一致。",
        "natal_author_timeliness_inconsistent": "玄空作者基本时令或互用数字与原盘星数及评价运不一致。",
        "natal_host_guest_inconsistent": "玄空主客盘层、星数、生克出入或原文对照不一致。",
        "monthly_plate_inconsistent": "月紫白有效年、节月、原表入中数、九宫飞布或区间表示不一致。",
    }

    def __init__(self, reason: str) -> None:
        if reason not in self.MESSAGES:
            raise ValueError("Unknown Feng Shui calculation consistency reason")
        self.reason = reason
        super().__init__(self.MESSAGES[reason])

    def as_result(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "error_code": "fengshui_calculation_inconsistent",
            "status_code": 503,
            "retryable": False,
            "issues": [
                {
                    "path": (
                        "runtime.fengshui.monthly_stars"
                        if self.reason == "monthly_plate_inconsistent"
                        else (
                            "runtime.fengshui.interpretation"
                            if self.reason
                            in {
                                "natal_mutual_geometry_inconsistent",
                                "natal_author_timeliness_inconsistent",
                                "natal_host_guest_inconsistent",
                            }
                            else "runtime.fengshui.natal_chart"
                        )
                    ),
                    "code": self.reason,
                }
            ],
        }


class JyotishCalculationError(RuntimeError):
    """An internal natal-evidence contradiction is not a bad birth input."""

    MESSAGES = {
        "drik_chain_inconsistent": "印占相位力证据与本次D1计算不一致，需维护者核查。",
    }

    def __init__(self, reason: str) -> None:
        if reason not in self.MESSAGES:
            raise ValueError("Unknown Jyotish calculation consistency reason")
        self.reason = reason
        super().__init__(self.MESSAGES[reason])

    def as_result(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "error_code": "jyotish_calculation_inconsistent",
            "status_code": 503,
            "retryable": False,
            "issues": [{"path": "runtime.jyotish.drik_bala", "code": self.reason}],
        }


class EphemerisSourceError(ValueError):
    """Safe, enumerated data-consistency failure; no paths or personal input."""

    MESSAGES = {
        "solar_native_unavailable": "Selected native solar model could not solve the requested crossing; no linear approximation is returned",
        "solar_term_source_unverified": "Solar-term crossing lacks a verified current model and source record; no approximate boundary is returned",
        "horizon_direction_model_unavailable": "Eastern horizon direction requires a valid coherent native house-angle model",
        "house_projection_precision_unavailable": "House-plane direction or its half-open house could not be resolved at the available working precision",
        "horizon_direction_precision_unavailable": "Eastern horizon endpoint direction could not be resolved at the available working precision",
        "swiss_dependency_unavailable": "A SWIEPH physical observation lacks complete observed planet and Moon file coverage; its top-level flag cannot exclude an analytical Moon dependency",
        "required_data_files_fallback": "require_data_files rejects an analytical, orbital or unidentified physical-coordinate model",
        "required_data_files_unavailable": "require_data_files could not obtain a requested physical coordinate or its data file",
        "required_data_files_unverified": "require_data_files could not verify the observed physical source context or private-worker policy",
        "ren_solar_term_longitude_inconsistent": "Consumed Liu Ren or Jin Kou solar-term name, numerical bracket or source does not match the declared model's forward solar-longitude crossing",
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
        "auxiliary_changed_during": "Native time auxiliary search candidates changed during the calculation",
        "auxiliary_unavailable": "Native time auxiliary source could not be inspected",
        "birth_clock_source_mismatch": "Birth-clock conversion and physical calculation use inconsistent Sun sources or time-scale mappings; resolve the original clock under one coherent configuration",
        "timezone_rules_changed": "Named timezone data changed after its rules were loaded; restore consistent data and restart the runtime",
        "timezone_rules_unavailable": "Declared named timezone data could not be read",
        "timezone_rules_invalid": "Declared named timezone data is not a valid TZif rule set",
        "human_design_reference_changed": "Human Design reference data changed after loading; restore consistent data and restart the runtime",
        "human_design_reference_unavailable": "Human Design reference data could not be read",
        "human_design_reference_invalid": "Human Design reference data is not a valid unambiguous JSON object",
        "human_design_reference_identity_mismatch": "Human Design reference bytes differ from the reviewed factual catalogue",
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
        "opaque_solar_light_time_not_stabilized": "Opaque-Sun light time did not stabilize at the available TT precision",
        "coordinate_motion_unavailable": "Native ephemeris did not provide the requested finite longitude motion",
        "point_mass_requires_barycentric_file_states": "Explicit Sun monopole comparison requires actual barycentric file states; analytical fallback is not accepted",
        "point_mass_light_time_did_not_stabilize": "Explicit Sun monopole light time did not stabilize at the available TT precision",
        "jpl_filename_invalid": "Strict JPL kernel must be a short basename in the configured ephemeris search path",
        "jpl_file_unavailable": "Selected strict JPL kernel could not be opened",
        "jpl_kernel_invalid": "Selected strict JPL kernel is not a complete supported DE441 direct-access file",
        "jpl_kinematics_invalid": "Selected DE441 source record or analytic kinematic inputs are invalid",
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
        "fictitious_changed_during": "Fictitious orbit source changed during factor calculation",
        "fictitious_changed_across": "Fictitious orbit source changed across birth-time samples",
        "fictitious_nominal_mismatch": "Fictitious orbit source differs between nominal chart and birth-time samples",
        "fictitious_identity": "Fictitious element slot does not identify the requested Hamburg factor; cannot label an unrelated orbit as a Hamburg factor",
    }

    def __init__(self, reason: str) -> None:
        if reason not in self.MESSAGES:
            raise ValueError("Unknown physical-ephemeris consistency reason")
        self.reason = reason
        super().__init__(self.MESSAGES[reason])

    def as_result(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "error_code": "ephemeris_source_inconsistent",
            "status_code": 503,
            "retryable": False,
            "issues": [{"path": "runtime.ephemeris_data", "code": self.reason}],
        }


class ValidationIssue(BaseModel):
    """Safe correction hints: never include submitted values or raw messages."""

    path: str
    code: str
    constraints: Optional[Dict[str, Any]] = None


class ErrorEnvelope(BaseModel):
    error: Any
    error_code: str
    retryable: bool
    issues: Optional[List[ValidationIssue]] = None
    trace_id: Optional[str] = None
    parent_run_id: Optional[str] = None


class ParameterError(ValueError):
    """Safe transport-independent rejection of non-model call parameters."""

    def __init__(self, message: str, issues: List[Dict[str, Any]]) -> None:
        super().__init__(message)
        self.issues = issues

    def as_result(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "error_code": VALIDATION_ERROR_CODE,
            "status_code": 422,
            "retryable": False,
            "issues": self.issues,
        }


def validation_error_result(error: Any) -> Dict[str, Any]:
    """Normalize Pydantic/FastAPI validation without echoing personal input."""
    entries = error.errors()
    # A model-level native time check can raise a source error. Pydantic wraps
    # ValueError subclasses in ctx.error; retain the enumerated runtime failure
    # instead of incorrectly blaming otherwise valid birth input. Only the
    # actual exception type is trusted, never submitted text or ctx dictionaries.
    if not any(item["type"] == "consultation_restricted" for item in entries):
        for item in entries:
            cause = (item.get("ctx") or {}).get("error")
            if isinstance(cause, EphemerisSourceError):
                return cause.as_result()
    issues = []
    restricted = False
    for item in entries:
        loc = list(item.get("loc", ()))
        if loc and loc[0] in {"body", "query"}:
            loc.pop(0)
        context = item.get("ctx") or {}
        constraints = {
            key: context[key]
            for key in ("ge", "gt", "le", "lt", "min_length", "max_length", "expected")
            if key in context
        }
        path = ".".join(str(part) for part in loc)
        if item["type"] == "consultation_restricted":
            restricted = True
            path = context.get("path", "request")
            constraints = {"policy": context["policy"]}
        if item["type"] == "invalid_calendar_date":
            path = context.get("prefix", "date") + "date"
        issue = {"path": path or "request", "code": item["type"]}
        if constraints:
            issue["constraints"] = constraints
        issues.append(issue)
    message = "此请求超出允许的咨询范围" if restricted else "请求参数无效"
    if not restricted and any(
        item["type"] == "unsupported_house_system" for item in entries
    ):
        from fatebridge.utils.house_systems import GAUQUELIN_UNSUPPORTED_MESSAGE

        message = GAUQUELIN_UNSUPPORTED_MESSAGE
    elif not restricted and any(
        item["type"] == "invalid_house_system" for item in entries
    ):
        from fatebridge.utils.house_systems import INVALID_HOUSE_SYSTEM_MESSAGE

        message = INVALID_HOUSE_SYSTEM_MESSAGE
    elif not restricted and any(
        item["type"] == "invalid_house_code" for item in entries
    ):
        from fatebridge.utils.house_systems import INVALID_HOUSE_CODE_MESSAGE

        message = INVALID_HOUSE_CODE_MESSAGE
    elif not restricted and any(
        item["type"] == "unresolved_timezone_offset" for item in entries
    ):
        message = UNRESOLVED_OFFSET_MESSAGE
    return {
        "error": message,
        "error_code": (
            "consultation_restricted" if restricted else VALIDATION_ERROR_CODE
        ),
        "status_code": 422,
        "retryable": False,
        "issues": issues,
    }


DEPENDENCY_ERROR_HINTS = (
    "no module named",
    "module not found",
    "missing dependency",
    "dependency missing",
    "swisseph",
    "ephemeris",
    "kerykeion",
    "依赖缺失",
    "未安装",
)


def handle_calculation_error(error: Exception, operation: str) -> Dict[str, Any]:
    """统一的错误处理函数

    Logs full error server-side but returns generic message to client
    for security reasons.

    Args:
        error: 异常对象
        operation: 操作名称

    Returns:
        包含错误信息的字典（不暴露内部细节）
    """
    error_text = str(error).strip()
    normalized = error_text.casefold()

    if isinstance(error, JyotishCalculationError):
        logger.error(
            "%s rejected inconsistent Jyotish computation: %s", operation, error.reason
        )
        return error.as_result()

    if isinstance(error, FengshuiCalculationError):
        logger.error(
            "%s rejected inconsistent Feng Shui computation: %s",
            operation,
            error.reason,
        )
        return error.as_result()

    if isinstance(error, NumerologySourceError):
        logger.error(
            "%s rejected inconsistent numerology sources: %s", operation, error.reason
        )
        return error.as_result()

    if isinstance(error, EphemerisSourceError):
        logger.warning(
            "%s rejected inconsistent ephemeris data: %s", operation, error_text
        )
        return error.as_result()

    if isinstance(error, (ImportError, ModuleNotFoundError)) or any(
        hint in normalized for hint in DEPENDENCY_ERROR_HINTS
    ):
        logger.error(f"{operation} failed: {error_text}", exc_info=True)
        return {
            "error": f"{operation}所需依赖缺失，请检查运行环境",
            "error_code": DEPENDENCY_ERROR_CODE,
            "status_code": 503,
            "retryable": False,
        }

    if isinstance(error, (TimeoutError, BuiltinTimeoutError)):
        logger.error(f"{operation} failed: {error_text}", exc_info=True)
        return {
            "error": f"{operation}处理超时，请稍后重试",
            "error_code": TIMEOUT_ERROR_CODE,
            "status_code": 504,
            "retryable": True,
        }

    if (
        isinstance(error, PydanticCustomError)
        and error.type == "unresolved_timezone_offset"
    ):
        logger.warning("%s rejected an unspecified timezone offset", operation)
        return {
            "error": UNRESOLVED_OFFSET_MESSAGE,
            "error_code": VALIDATION_ERROR_CODE,
            "status_code": 422,
            "retryable": False,
            "issues": [{"path": "request", "code": error.type}],
        }

    if isinstance(error, ValueError):
        # User/domain input rejection (HTTP 400), not a system fault. Log a
        # concise warning without a stack trace — dumping a full traceback for
        # every "invalid date" or "unknown hexagram name" floods the error log
        # with noise that looks like a crash.
        logger.warning(f"{operation} rejected invalid input: {error_text}")
        return {
            "error": error_text or f"{operation}输入无效",
            "error_code": VALIDATION_ERROR_CODE,
            "status_code": 400,
            "retryable": False,
        }

    # Unexpected internal fault — this is the one case that warrants a full
    # stack trace at ERROR level for server-side diagnosis.
    logger.error(f"{operation} failed: {error_text}", exc_info=True)
    return {
        "error": f"{operation}暂时不可用，请稍后重试",
        "error_code": INTERNAL_ERROR_CODE,
        "status_code": 500,
        "retryable": True,
    }


def calculation_guard(
    operation: str,
) -> Callable[[Callable[_P, Dict[str, Any]]], Callable[_P, Dict[str, Any]]]:
    """将服务函数包裹为"任何异常都转成标准错误信封"的形式。

    与此前散落在 ~50 个服务调用点的手写写法在行为上完全一致::

        try:
            ...函数体...
        except Exception as exc:
            return handle_calculation_error(exc, operation)

    只适用于"整个函数体都在 try 内、except 是最后一步"的场景；
    若函数在 try 之前另有语句，请勿迁移（包裹整函数会吞掉本应向上抛出的异常）。

    Args:
        operation: 操作名称，原样透传给 :func:`handle_calculation_error`
            （它是错误信封的一部分，必须与迁移前的字符串逐字一致）。
    """

    def decorator(
        func: Callable[_P, Dict[str, Any]],
    ) -> Callable[_P, Dict[str, Any]]:
        @wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Dict[str, Any]:
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - 故意宽捕获，与迁移前行为一致
                return handle_calculation_error(exc, operation)

        return wrapper

    return decorator


def error_response_payload(data: Dict[str, Any], operation: str) -> Dict[str, Any]:
    """The shared JSON error envelope used by all transports."""
    return {
        "error": data["error"],
        "error_code": data.get("error_code", INTERNAL_ERROR_CODE),
        "status_code": data.get("status_code", 500),
        "retryable": data.get("retryable", False),
        "operation": operation,
        **({"issues": data["issues"]} if "issues" in data else {}),
        **({"trace_id": data["trace_id"]} if "trace_id" in data else {}),
        **({"parent_run_id": data["parent_run_id"]} if "parent_run_id" in data else {}),
    }
