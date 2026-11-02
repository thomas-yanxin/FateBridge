"""The only allowed historical proof changes after the shared v5 definition.

Original packets/proofs stay immutable. An older complete static declaration
can be valid while no longer describing the current implementation. Every
other field in each historical proof must still compare exactly.
"""

import json
from copy import deepcopy
from pathlib import Path

VARIANTS = json.loads(
    (
        Path(__file__).parent
        / "fixtures/human-design-native-declaration-v5-variants.json"
    ).read_text()
)


def static_policy(policy):
    return {k: v for k, v in policy.items() if k not in VARIANTS["dynamic_fields"]}


def expected_historical_proof(packet, original_proof):
    expected = deepcopy(original_proof)
    policy = packet["native_execution_context"]["compressed_file_endpoint_policy"]
    if static_policy(policy) == VARIANTS["old_static"]:
        meta = expected["native_execution_policy"]
        assert meta["matches_current_declared_policy"] is True
        assert meta["historical_declared_policy_verified"] is False
        meta["matches_current_declared_policy"] = VARIANTS[
            "legacy_expected_matches_current"
        ]
        meta["historical_declared_policy_verified"] = VARIANTS[
            "legacy_expected_historical_verified"
        ]
    return expected
