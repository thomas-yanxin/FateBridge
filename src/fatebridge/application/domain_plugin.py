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
    """Flatten registered domain plugins while enforcing unique tool keys."""
    catalog: list[ToolSpec] = []
    seen_keys: set[str] = set()
    for plugin in plugins:
        for spec in plugin.specs:
            if spec.key in seen_keys:
                raise ValueError(f"Duplicate key {spec.key} in domain {plugin.name}")
            else:
                pass
            seen_keys.add(spec.key)
            catalog.append(spec)
    return catalog
