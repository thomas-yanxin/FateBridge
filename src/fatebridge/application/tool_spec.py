"""Transport-independent declarations for one catalog tool."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple, Type

from pydantic import BaseModel

from fatebridge.core.method_contracts import MethodContract
from fatebridge.core.reproducibility import ReproducibilityPolicy

ServiceResult = Dict[str, Any]
# A bind turns a validated request model into a concrete service call:
#   (service_callable, positional_args, keyword_args)
# The shared execution unit invokes this binding (REST offloads the unit to a
# threadpool; MCP/CLI call it synchronously), keeping domain work off the event
# loop while freezing time and attaching receipts consistently.
Bind = Callable[[BaseModel], Tuple[Callable[..., ServiceResult], tuple, Dict[str, Any]]]


@dataclass(frozen=True)
class ExecutionHints:
    """Environment effects, independent of numerical output determinism."""

    read_only: bool = True
    destructive: bool = False
    idempotent: bool = True
    open_world: bool = False

    def as_annotations(self) -> Dict[str, bool]:
        return {
            "readOnlyHint": self.read_only,
            "destructiveHint": self.destructive,
            "idempotentHint": self.idempotent,
            "openWorldHint": self.open_world,
        }


@dataclass(frozen=True)
class ToolSpec:
    """Single source of truth for one FateBridge tool across all surfaces."""

    key: str
    bind: Bind
    request_model: Type[BaseModel]
    summary: str
    operation_label_zh: str
    family: str
    rest_path: Optional[str] = None
    mcp_name: Optional[str] = None
    cpu_bound: bool = False
    include_snapshot_text: bool = True
    error_is_fatal: Optional[Callable[[ServiceResult], bool]] = None
    rest_error_label: Optional[str] = None
    metadata_name: Optional[str] = None
    output_model: Optional[Type[BaseModel]] = None
    # Complete service results are validated before projection. Public output
    # schemas allow omissions for fields selections, but a service must still
    # produce its declared non-null business roots.
    required_output_fields: Tuple[str, ...] = ()
    cli_request_file: bool = False
    execution_hints: ExecutionHints = field(default_factory=ExecutionHints)
    reproducibility: ReproducibilityPolicy = field(
        default_factory=ReproducibilityPolicy
    )
    methods: Tuple[MethodContract, ...] = ()

    @property
    def tool_name(self) -> str:
        return self.mcp_name or self.key

    @property
    def run_metadata_name(self) -> str:
        """The tool_name stamped into run_metadata (may differ from the registered name)."""
        return self.metadata_name or self.mcp_name or self.key
