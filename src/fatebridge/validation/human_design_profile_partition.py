"""Replay the nominal solar-role partition without any ephemeris call."""

from typing import Any

from fatebridge.core.human_design_profile_partition import (
    profile_partition_report,
)
from fatebridge.core.public_output import same_public_value as _same_value


def checked_profile_partition(payload: dict[str, Any]) -> dict[str, Any]:
    expected = profile_partition_report(payload)
    if not _same_value(payload["profile_partition_context"], expected):
        raise ValueError("Profile partition source, arithmetic or actual role mismatch")
    return expected
