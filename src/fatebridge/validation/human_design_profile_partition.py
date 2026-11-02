"""Replay the nominal solar-role partition without any ephemeris call."""

from typing import Any

from fatebridge.core.human_design_profile_partition import (
    METHOD,
    profile_partition_report,
)
from fatebridge.validation.claims import _same_value

# Exact pre-extension schema identities, never case IDs. A current or unknown
# contract cannot hide the extension by deleting all of its output regions.
PRE_PARTITION_CONTRACTS = frozenset(
    {
        "30e391eb24c92dc5b61f9f27b296536cc5891c34367b73e7cc33daee91b8f765",
        "168d79463454686ee3e8afb731ea2ee8d29ae906f0d9ca88c5cf364ea7daba30",
        "570410131790378bf9a4e34e1f7031d5767e6dd9103c88426746099d870400b2",
        "56806b2004d57149ad0067f1e7cb090d4fd3325413a6f21b04b4dc91dd02d4aa",
    }
)


def declares_legacy_partition_contract(payload: dict[str, Any]) -> bool:
    if (
        payload.get("run_metadata", {}).get("contract_sha256")
        not in PRE_PARTITION_CONTRACTS
    ):
        return False
    if (
        "profile_partition_context" in payload
        or "profile_partition_context" in payload.get("interpretation", {})
        or "profile_partition_context"
        in payload.get("interpretation", {}).get("basis", [])
    ):
        return False
    return not any(
        any(row.get(k) == METHOD for k in ("id", "rule_id", "ruleset_id"))
        for key in ("rulesets", "rule_trace")
        for row in payload.get(key, [])
    )


def checked_profile_partition(payload: dict[str, Any]) -> dict[str, Any]:
    expected = profile_partition_report(payload)
    if not _same_value(payload["profile_partition_context"], expected):
        raise ValueError("Profile partition source, arithmetic or actual role mismatch")
    return expected
