"""Only known pre-extension schemas may omit the historical comparison."""

from typing import Any

from fatebridge.core.human_design_historical_polarity import METHOD

PRE_HISTORICAL_POLARITY_CONTRACTS = frozenset(
    {
        "fa56c62beed008e190217f69fc8eb89f7abe858c5a4c46fb0d0ac0e77c6c93d4",
        "f66b042abb0a9b04261477989e147609fc9b011cea0e4613fb4183e6c483ae7e",
        "30e391eb24c92dc5b61f9f27b296536cc5891c34367b73e7cc33daee91b8f765",
        "168d79463454686ee3e8afb731ea2ee8d29ae906f0d9ca88c5cf364ea7daba30",
        "570410131790378bf9a4e34e1f7031d5767e6dd9103c88426746099d870400b2",
        "56806b2004d57149ad0067f1e7cb090d4fd3325413a6f21b04b4dc91dd02d4aa",
    }
)


def declares_legacy_historical_polarity_contract(payload: dict[str, Any]) -> bool:
    if (
        payload.get("run_metadata", {}).get("contract_sha256")
        not in PRE_HISTORICAL_POLARITY_CONTRACTS
    ):
        return False
    interpretation = payload.get("interpretation", {})
    if (
        "historical_polarity_context" in payload
        or "historical_polarity_context" in interpretation
        or "historical_polarity_context" in interpretation.get("basis", [])
    ):
        return False
    return not any(
        any(row.get(k) == METHOD for k in ("id", "rule_id", "ruleset_id"))
        for key in ("rulesets", "rule_trace")
        for row in payload.get(key, [])
    )
