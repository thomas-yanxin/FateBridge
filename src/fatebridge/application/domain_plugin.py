"""Declarative domain plugin contract for FateBridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from fatebridge.application.tool_spec import ToolSpec


@dataclass(frozen=True)
class DomainPlugin:
    """One self-contained calculation domain registered into the shared engine."""

    name: str
    specs: tuple[ToolSpec, ...]


def assemble_catalog(plugins: Sequence[DomainPlugin]) -> list[ToolSpec]:
    """Flatten registered domain plugins while enforcing unique tool names."""
    catalog: list[ToolSpec] = []
    seen_names: set[str] = set()
    for plugin in plugins:
        for spec in plugin.specs:
            if spec.name in seen_names:
                raise ValueError(f"Duplicate tool {spec.name} in domain {plugin.name}")
            seen_names.add(spec.name)
            catalog.append(spec)
    return catalog
