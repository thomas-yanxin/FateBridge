"""Verify inline business facts when a large runtime receipt is referenced."""

import json

from tests.fixtures.mcp_result_delivery import read_full_result


async def verified_inline_business(client, payload):
    assert len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))) <= 8192
    delivery = payload.get("result_delivery")
    if delivery is None:
        return payload
    # This is never permission to hide a star, position, source row or other
    # business result behind pagination in a first-view budget assertion.
    deferred = delivery["deferred_fields"]
    assert deferred and len(deferred) == len(set(deferred)), delivery
    assert set(deferred) <= {
        "run_metadata.runtime",
        "run_metadata.provenance",
        "run_metadata.determinism",
        "run_metadata.calculation_evidence",
    }, delivery
    full = await read_full_result(client, payload)
    inline = {
        k: v for k, v in payload.items() if k not in ("run_metadata", "result_delivery")
    }
    stored = {k: v for k, v in full.items() if k != "run_metadata"}
    assert inline == stored
    return {**inline, "run_metadata": full["run_metadata"]}
