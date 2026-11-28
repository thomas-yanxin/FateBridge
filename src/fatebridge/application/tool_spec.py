"""Transport-independent declarations for one catalog tool."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Protocol, runtime_checkable

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    from decimal import Decimal

    from pydantic import BaseModel

    from fatebridge.core.reproducibility import ReproducibilityPolicy
    from fatebridge.utils.birth_input import PersonInfo

ServiceResult = dict[str, Any]
if TYPE_CHECKING:
    ServiceInput = (
        str
        | int
        | float
        | bool
        | Decimal
        | None
        | Sequence["ServiceInput"]
        | Mapping[str, "ServiceInput"]
        | Mapping[int, "ServiceInput"]
    )
    ServicePositionalInput = ServiceInput | PersonInfo | BaseModel
else:
    ServiceInput = Any
    ServicePositionalInput = Any


class EvidenceView(TypedDict):
    fields: list[str]
    when: NotRequired[str]
    purpose: NotRequired[str]
    description: NotRequired[str]
    label: NotRequired[str]
    relative_mode: NotRequired[str]
    primary_layer: NotRequired[str]
    scope: NotRequired[str]
    aliases: NotRequired[list[str | int]]


EvidenceViews = dict[str, EvidenceView]


@runtime_checkable
class ResolvedService(Protocol):
    """Domain entry point as exposed to the dynamic registration boundary."""

    def __call__(
        self, *positional: ServicePositionalInput, **keywords: ServiceInput
    ) -> ServiceResult: ...


class BoundServiceCall(NamedTuple):
    service: ResolvedService
    positional_arguments: tuple[ServicePositionalInput, ...]
    keyword_arguments: dict[str, ServiceInput]


class Bind(Protocol):
    """Bind a validated request to its service and arguments."""

    def __call__(
        self, request: BaseModel, /
    ) -> tuple[
        ResolvedService, tuple[ServicePositionalInput, ...], dict[str, ServiceInput]
    ]: ...


class RunService(Protocol):
    def __call__(self) -> ServiceResult: ...


class OutputValidator(Protocol):
    def __call__(
        self,
        spec: ToolSpec,
        result: ServiceResult,
        request: BaseModel | None,
        validated: BaseModel | None,
        /,
    ) -> None: ...


class RequiredOutputValidator(Protocol):
    def __call__(
        self, spec: ToolSpec, result: ServiceResult, request: BaseModel | None, /
    ) -> None: ...


class ExecutionWrapper(Protocol):
    def __call__(
        self, spec: ToolSpec, request: BaseModel, run: RunService, /
    ) -> ServiceResult: ...


class EvidenceViewsBuilder(Protocol):
    def __call__(self, views: EvidenceViews | None, /) -> EvidenceViews | None: ...


class NeedsRandomSeed(Protocol):
    def __call__(self, arguments: dict[str, ServiceInput], /) -> bool: ...


class TimeDefaultsResolver(Protocol):
    def __call__(
        self, result: ServiceResult, omitted_fields: list[str], /
    ) -> list[str]: ...


class ApproximationDetector(Protocol):
    def __call__(self, result: ServiceResult, /) -> bool: ...


class OutputContractError(RuntimeError):
    """A service bug, never a user-input error."""


@dataclass(frozen=True)
class ExecutionHints:
    """Environment effects, independent of numerical output determinism."""

    read_only: bool = True
    destructive: bool = False
    open_world: bool = False

    def as_annotations(self) -> dict[str, bool]:
        return {
            "readOnlyHint": self.read_only,
            "destructiveHint": self.destructive,
            "openWorldHint": self.open_world,
        }


@dataclass(frozen=True)
class BatchInputPolicy:
    """Declarative batch subject and shared context mapping policy for one tool."""

    subject_mode: Literal[
        "none",
        "birth_fields",
        "date_clock",
        "exclusive_birth_record",
        "subject_list",
        "pair",
    ] = "none"
    list_field: str | None = None
    pair_prefixes: tuple[str, str] | tuple[()] = ()
    pair_style: Literal["birth_fields", "date_zone"] = "birth_fields"
    context_prefixes: tuple[str, ...] = ("analysis_",)
    context_clock_basis_field: str | None = None
    solar_clock_bases: tuple[str, ...] = ()


_UNSET_OUTPUT_MODEL: Any = object()
_UNSET_REQUEST_MODEL: Any = object()


@dataclass(frozen=True)
class ToolSpec:
    """Single source of truth for one FateBridge tool across all surfaces."""

    name: str
    bind: Bind
    summary: str
    operation_label_zh: str
    family: str
    request_model: type[BaseModel] = _UNSET_REQUEST_MODEL
    request_model_loader: Callable[[], type[BaseModel]] | None = field(
        default=None, repr=False, compare=False
    )
    rest_path: str | None = None
    expose_mcp: bool = True
    cpu_bound: bool = False
    output_model: type[BaseModel] | None = _UNSET_OUTPUT_MODEL
    output_model_loader: Callable[[], type[BaseModel] | None] | None = field(
        default=None, repr=False, compare=False
    )
    # note (output validation): Complete service results must include these roots before projection.
    required_output_fields: tuple[str, ...] = ()
    output_fields: tuple[str, ...] = ()
    required_output_validator: RequiredOutputValidator | None = None
    cli_request_file: bool = False
    execution_hints: ExecutionHints = field(default_factory=ExecutionHints)
    reproducibility: ReproducibilityPolicy | None = None
    output_validators: tuple[OutputValidator, ...] = ()
    needs_random_seed: NeedsRandomSeed | None = None
    resolve_time_defaults: TimeDefaultsResolver | None = None
    approximate_record: ApproximationDetector | None = None
    uses_astronomy_runtime: bool = True
    execution_wrapper: ExecutionWrapper | None = None
    evidence_views_builder: EvidenceViewsBuilder | None = None
    default_omit: tuple[str, ...] = ()
    batch_policy: BatchInputPolicy = field(default_factory=BatchInputPolicy)

    def __getattribute__(self, name: str) -> Any:
        if name == "output_model":
            attrs = object.__getattribute__(self, "__dict__")
            value = attrs.get("output_model", _UNSET_OUTPUT_MODEL)
            if value is _UNSET_OUTPUT_MODEL:
                loader = attrs.get("output_model_loader")
                if loader is None:
                    return None
                value = loader()
                object.__setattr__(self, "output_model", value)
            return value
        if name == "request_model":
            attrs = object.__getattribute__(self, "__dict__")
            value = attrs.get("request_model", _UNSET_REQUEST_MODEL)
            if value is _UNSET_REQUEST_MODEL:
                loader = attrs.get("request_model_loader")
                if loader is None:
                    raise AttributeError("ToolSpec missing request_model")
                value = loader()
                object.__setattr__(self, "request_model", value)
            return value
        return object.__getattribute__(self, name)
