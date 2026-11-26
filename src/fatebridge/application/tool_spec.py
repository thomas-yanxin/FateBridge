"""Transport-independent declarations for one catalog tool."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, NamedTuple, Protocol, runtime_checkable

from pydantic import BaseModel
from typing_extensions import NotRequired, TypedDict

from fatebridge.core.execution_context import DetailLevel
from fatebridge.core.method_contracts import MethodContract
from fatebridge.core.reproducibility import ReproducibilityPolicy
from fatebridge.utils.birth_input import PersonInfo

ServiceResult = dict[str, Any]
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
ServicePositionalInput = ServiceInput | PersonInfo


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


class CompactView(Protocol):
    def __call__(self, result: ServiceResult, /) -> ServiceResult: ...


class DetailView(Protocol):
    def __call__(
        self, result: ServiceResult, detail: DetailLevel, requested_fields: set[str], /
    ) -> ServiceResult: ...


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
class ToolSpec:
    """Single source of truth for one FateBridge tool across all surfaces."""

    name: str
    bind: Bind
    request_model: type[BaseModel]
    summary: str
    operation_label_zh: str
    family: str
    rest_path: str | None = None
    expose_mcp: bool = True
    cpu_bound: bool = False
    output_model: type[BaseModel] | None = None
    # note (output validation): Complete service results must include these roots before projection.
    required_output_fields: tuple[str, ...] = ()
    required_output_validator: RequiredOutputValidator | None = None
    cli_request_file: bool = False
    execution_hints: ExecutionHints = field(default_factory=ExecutionHints)
    reproducibility: ReproducibilityPolicy = field(
        default_factory=ReproducibilityPolicy
    )
    methods: tuple[MethodContract, ...] = ()
    output_validators: tuple[OutputValidator, ...] = ()
    needs_random_seed: NeedsRandomSeed | None = None
    resolve_time_defaults: TimeDefaultsResolver | None = None
    approximate_record: ApproximationDetector | None = None
    uses_astronomy_runtime: bool = False
    execution_wrapper: ExecutionWrapper | None = None
    evidence_views_builder: EvidenceViewsBuilder | None = None
    compact_view: CompactView | None = None
    detail_view: DetailView | None = None
