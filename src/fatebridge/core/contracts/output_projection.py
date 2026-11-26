"""Projection-compatible root output contract."""

from fatebridge.core.contracts.output_base import PartialOutput


class ProjectedOutput(PartialOutput):
    """Base contract for tool output models supporting field projection."""
