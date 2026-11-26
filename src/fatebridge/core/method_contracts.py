"""Declared method semantics; registration never implies domain acceptance."""

from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue


@dataclass(frozen=True)
class MethodContract:
    method_id: str
    output_paths: tuple[str, ...]
    quantity_kind: str
    unit: str
    prerequisites: tuple[str, ...]
    dependencies: tuple[str, ...]
    comparison_requirements: tuple[str, ...]
    limitations: tuple[str, ...]
    role: Literal["calculation", "reference", "presentation"] = "calculation"
    implementation_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    selector_fields: tuple[str, ...] = ()
    error_sources: tuple[str, ...] = ()
    validation_status: str = "not_fully_accepted"
    requires_non_null_output: str | None = None

    def as_manifest(self) -> dict[str, JsonValue]:
        return {
            "method_id": self.method_id,
            "output_paths": list(self.output_paths),
            "quantity_kind": self.quantity_kind,
            "unit": self.unit,
            "prerequisites": list(self.prerequisites),
            "dependencies": list(self.dependencies),
            "comparison_requirements": list(self.comparison_requirements),
            "limitations": list(self.limitations),
            "role": self.role,
            "implementation_refs": list(self.implementation_refs),
            "source_refs": list(self.source_refs),
            "selector_fields": list(self.selector_fields),
            "error_sources": list(self.error_sources),
            **(
                {"requires_non_null_output": self.requires_non_null_output}
                if self.requires_non_null_output is not None
                else {}
            ),
            "validation_scope": {
                "numerical": "method_specific_reference_required",
                "source_conformity": self.validation_status,
                "real_world_validity": "not_established",
            },
        }
