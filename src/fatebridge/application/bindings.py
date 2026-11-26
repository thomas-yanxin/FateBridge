"""Resolve catalog services when binding a validated request."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from importlib import import_module
from inspect import signature
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from fatebridge.application.tool_spec import (
    Bind,
    BoundServiceCall,
    ResolvedService,
    ServiceInput,
    ServicePositionalInput,
    ServiceResult,
)
from fatebridge.utils.birth_input import PersonInfo


@dataclass(frozen=True)
class ServiceRef:
    """Reference a service module without loading it during discovery."""

    module_name: str
    service_name: str

    @cached_property
    def resolved(self) -> ResolvedService:
        service: object = getattr(import_module(self.module_name), self.service_name)
        if isinstance(service, ResolvedService):
            return service
        else:
            raise TypeError(f"{self.module_name}.{self.service_name} is not a service")

    def __call__(
        self, *positional: ServicePositionalInput, **keywords: ServiceInput
    ) -> ServiceResult:
        return self.resolved(*positional, **keywords)


def service_ref(module: str, name: str) -> ServiceRef:
    return ServiceRef(module, name)


def resolve_service(service: ServiceRef | ResolvedService) -> ResolvedService:
    return service.resolved if isinstance(service, ServiceRef) else service


PERSON_FIELDS = frozenset(
    {
        "birth_year",
        "birth_month",
        "birth_day",
        "birth_hour",
        "name",
        "gender",
        "birth_place",
        "birth_minute",
        "birth_second",
        "birth_timezone",
        "birth_utc_offset",
        "birth_longitude",
        "use_true_solar_time",
    }
)


def _build_person(
    data: Mapping[str, ServiceInput],
    prefix: str = "",
    *,
    true_solar_explicit: bool = True,
    supplied_fields: set[str] | None = None,
) -> PersonInfo:
    person_arguments = {
        "name": data.get(f"{prefix}name", "未提供"),
        "birth_year": data.get(f"{prefix}birth_year"),
        "birth_month": data.get(f"{prefix}birth_month"),
        "birth_day": data.get(f"{prefix}birth_day"),
        "birth_hour": data.get(f"{prefix}birth_hour"),
        "gender": data.get(f"{prefix}gender", "未知"),
        "birth_place": data.get(f"{prefix}birth_place", "未提供"),
        "birth_timezone": data.get(f"{prefix}birth_timezone"),
        "birth_utc_offset": data.get(f"{prefix}birth_utc_offset"),
        "birth_longitude": data.get(f"{prefix}birth_longitude"),
        "use_true_solar_time": data.get(f"{prefix}use_true_solar_time", False),
        "true_solar_explicit": true_solar_explicit,
    }
    birth_minute = data.get(f"{prefix}birth_minute")
    birth_second = data.get(f"{prefix}birth_second")
    if birth_minute is not None and (
        supplied_fields is None or f"{prefix}birth_minute" in supplied_fields
    ):
        person_arguments["birth_minute"] = birth_minute
    if birth_second is not None:
        person_arguments["birth_second"] = birth_second
    return PersonInfo.model_validate(person_arguments)


def bind_person(
    service: ServiceRef | ResolvedService, *, also_pass: tuple[str, ...] = ()
) -> Bind:
    """Bind the birth input and forward the remaining validated request fields."""
    forwarded_person_fields = PERSON_FIELDS.difference(also_pass)

    def bind(request: BaseModel) -> BoundServiceCall:
        arguments: dict[str, ServiceInput] = request.model_dump()
        person = _build_person(
            arguments,
            true_solar_explicit="use_true_solar_time" in request.model_fields_set,
            supplied_fields=request.model_fields_set,
        )
        return BoundServiceCall(
            resolve_service(service),
            (person,),
            {
                field: value
                for field, value in arguments.items()
                if field not in forwarded_person_fields
            },
        )

    return bind


def bind_pair(
    service: ServiceRef | ResolvedService,
    *,
    relationship_field: str = "relationship_type",
) -> Bind:
    """Bind each person with independent clock presence."""

    def bind(request: BaseModel) -> BoundServiceCall:
        arguments: dict[str, ServiceInput] = request.model_dump()
        supplied_fields = request.model_fields_set
        person1 = _build_person(
            arguments,
            prefix="person1_",
            true_solar_explicit="person1_use_true_solar_time" in supplied_fields,
            supplied_fields=supplied_fields,
        )
        person2 = _build_person(
            arguments,
            prefix="person2_",
            true_solar_explicit="person2_use_true_solar_time" in supplied_fields,
            supplied_fields=supplied_fields,
        )
        relationship = arguments.get(relationship_field, "general")
        return BoundServiceCall(
            resolve_service(service), (person1, person2, relationship), {}
        )

    return bind


@runtime_checkable
class ServiceInputProvider(Protocol):
    def service_inputs(self) -> Mapping[str, ServiceInput]: ...


def bind_request(service: ServiceRef | ResolvedService) -> Bind:
    """Pass the validated request model directly as the single positional argument."""

    def bind(request: BaseModel) -> BoundServiceCall:
        return BoundServiceCall(
            resolve_service(service),
            (request,),  # type: ignore[arg-type]
            {},
        )

    return bind


def bind_kwargs(
    service: ServiceRef | ResolvedService,
    *,
    fixed: Mapping[str, ServiceInput] | None = None,
) -> Bind:
    """Forward validated service keywords, including declared clock presence."""
    accepts_explicit_solar_time: bool | None = None

    def bind(request: BaseModel) -> BoundServiceCall:
        nonlocal accepts_explicit_solar_time
        resolved = resolve_service(service)
        if accepts_explicit_solar_time is None:
            accepts_explicit_solar_time = (
                "true_solar_explicit" in signature(resolved).parameters
            )
        arguments: dict[str, ServiceInput] = (
            dict(request.service_inputs())
            if isinstance(request, ServiceInputProvider)
            else request.model_dump()
        )
        if accepts_explicit_solar_time:
            arguments["true_solar_explicit"] = (
                "use_true_solar_time" in request.model_fields_set
            )
        if fixed:
            arguments.update(fixed)
        return BoundServiceCall(resolved, (), arguments)

    return bind
