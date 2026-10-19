"""Standardised calculation error envelope + guard decorator.

Extracted verbatim from utils/helpers.py (god-file split). Pure error
formatting/control-flow — no numerical computation.
"""

import logging
from builtins import TimeoutError as BuiltinTimeoutError
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEPENDENCY_ERROR_CODE = "dependency_missing"
INTERNAL_ERROR_CODE = "internal_error"
TIMEOUT_ERROR_CODE = "timeout"
VALIDATION_ERROR_CODE = "validation_error"


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
    issues = []
    restricted = False
    for item in error.errors():
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
    return {
        "error": "此请求超出允许的咨询范围" if restricted else "请求参数无效",
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
) -> Callable[[Callable[..., Dict[str, Any]]], Callable[..., Dict[str, Any]]]:
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
        func: Callable[..., Dict[str, Any]],
    ) -> Callable[..., Dict[str, Any]]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
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
