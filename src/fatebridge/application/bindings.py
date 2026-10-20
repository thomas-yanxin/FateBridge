"""Lazy service resolution and validated request-to-service binding."""

import importlib
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel

from fatebridge.application.tool_spec import Bind, ServiceResult
from fatebridge.utils.birth_input import PersonInfo, create_person_info


def lazy_service(module: str, name: str) -> Callable[..., ServiceResult]:
    """Return a proxy that imports ``module`` and resolves ``name`` on first call.

    Lets the tool catalog declare a tool's service without importing the
    (sometimes heavy — e.g. the kerykeion-backed western modules) service module
    until that tool is actually invoked. The proxy carries an ``__fb_lazy__``
    marker so binders can resolve the real function before scheduling execution.
    """
    cell: List[Callable[..., ServiceResult]] = []

    def _proxy(*args: Any, **kwargs: Any) -> ServiceResult:
        if not cell:
            cell.append(getattr(importlib.import_module(module), name))
        return cell[0](*args, **kwargs)

    _proxy.__fb_lazy__ = (module, name)  # type: ignore[attr-defined]
    _proxy.__name__ = name
    _proxy.__qualname__ = name
    return _proxy


def resolve_service(service: Callable[..., Any]) -> Callable[..., Any]:
    """Return the real service callable, importing it if ``service`` is lazy."""
    marker = getattr(service, "__fb_lazy__", None)
    if marker is None:
        return service
    module, name = marker
    resolved: Callable[..., Any] = getattr(importlib.import_module(module), name)
    return resolved


def _resolver(
    service: Callable[..., ServiceResult],
) -> Callable[[], Callable[..., ServiceResult]]:
    """Memoise lazy-proxy resolution so a bind unwraps its service exactly once.

    Binders return the *resolved* domain function (not the proxy) so the unit of
    work handed to the surfaces — REST's threadpool, MCP/CLI's direct call — is
    the real service, while the import stays deferred until the first invocation.
    """
    cache: List[Callable[..., ServiceResult]] = []

    def get() -> Callable[..., ServiceResult]:
        if not cache:
            cache.append(resolve_service(service))
        return cache[0]

    return get


_PERSON_POSITIONAL = (
    "birth_year",
    "birth_month",
    "birth_day",
    "birth_hour",
    "name",
    "gender",
    "birth_place",
)
_PERSON_KEYWORD = (
    "birth_minute",
    "birth_timezone",
    "birth_longitude",
    "use_true_solar_time",
)


def _build_person(
    data: Dict[str, Any], prefix: str = "", *, true_solar_explicit: bool = True
) -> PersonInfo:
    def g(field: str, default: Any = None) -> Any:
        return data.get(f"{prefix}{field}", default)

    return create_person_info(
        g("birth_year"),
        g("birth_month"),
        g("birth_day"),
        g("birth_hour"),
        g("name", "未提供"),
        g("gender", "未知"),
        g("birth_place", "未提供"),
        birth_minute=g("birth_minute", 0),
        birth_timezone=g("birth_timezone"),
        birth_longitude=g("birth_longitude"),
        use_true_solar_time=g("use_true_solar_time", False),
        true_solar_explicit=true_solar_explicit,
    )


def person_invoke(
    service: Callable[..., ServiceResult], *, also_pass: Tuple[str, ...] = ()
) -> Bind:
    """Single-person tools: bind to service(person, **extras).

    ``extras`` is auto-derived as every request field that is NOT a standard
    person field, so a tool only needs to declare its model. ``also_pass`` adds
    back person fields that a service consumes a second time (e.g. a tool whose
    analysis step also honours ``use_true_solar_time``).
    """
    person_fields = set(_PERSON_POSITIONAL) | set(_PERSON_KEYWORD)
    get_service = _resolver(service)

    def _bind(
        req: BaseModel,
    ) -> Tuple[Callable[..., ServiceResult], tuple, Dict[str, Any]]:
        data = req.model_dump()
        # 区分「用户显式要求真太阳时」与「吃了模型默认」：缺经度时前者 fail-loud、
        # 后者降级为钟表时间并附 advisory（见 normalize_birth_time）。
        explicit = "use_true_solar_time" in req.model_fields_set
        person = _build_person(data, true_solar_explicit=explicit)
        extras = {k: v for k, v in data.items() if k not in person_fields}
        for field in also_pass:
            if field in data:
                extras[field] = data[field]
        return get_service(), (person,), extras

    return _bind


def pair_invoke(
    service: Callable[..., ServiceResult],
    *,
    relationship_field: str = "relationship_type",
) -> Bind:
    """Two-person compatibility: bind to service(person1, person2, relationship)."""
    get_service = _resolver(service)

    def _bind(
        req: BaseModel,
    ) -> Tuple[Callable[..., ServiceResult], tuple, Dict[str, Any]]:
        data = req.model_dump()
        fields_set = req.model_fields_set
        p1 = _build_person(
            data,
            prefix="person1_",
            true_solar_explicit="person1_use_true_solar_time" in fields_set,
        )
        p2 = _build_person(
            data,
            prefix="person2_",
            true_solar_explicit="person2_use_true_solar_time" in fields_set,
        )
        rel = data.get(relationship_field, "general")
        return get_service(), (p1, p2, rel), {}

    return _bind


def raw_invoke(
    service: Callable[..., ServiceResult],
    *,
    fixed: Optional[Dict[str, Any]] = None,
) -> Bind:
    """Bind every validated request field to the resolved service unchanged."""
    get_service = _resolver(service)
    explicit_solar_cache: List[bool] = []

    def _bind(
        req: BaseModel,
    ) -> Tuple[Callable[..., ServiceResult], tuple, Dict[str, Any]]:
        resolved = get_service()
        if not explicit_solar_cache:
            explicit_solar_cache.append(
                "true_solar_explicit" in inspect.signature(resolved).parameters
            )
        data = req.model_dump()
        # Thread whether the user explicitly asked for true solar time so the
        # service can fail-loud on an explicit request that lacks a longitude,
        # yet gracefully fall back to civil time when the flag merely defaulted
        # on (mirrors the person path in ``person_invoke``). Only inject into
        # services that explicitly declare the parameter — never into a
        # ``**kwargs`` dispatcher, which would forward the
        # unknown kwarg to an inner service that does not accept it.
        if explicit_solar_cache[0]:
            data["true_solar_explicit"] = "use_true_solar_time" in req.model_fields_set
        if fixed:
            data = {**data, **fixed}
        return resolved, (), data

    return _bind
