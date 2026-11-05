"""An archived request module and current lazy services reproduce the live fault."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_cached_options_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]


def test_archived_request_bytes_are_the_frozen_v18_module():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    for name, digest in m["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert m["expected_contract_generated_by_current_service"] is False


def test_fresh_options_still_accept_and_validate_the_new_observation_field():
    from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
    from fatebridge.services.meihua import calculate_meihua_cast

    assert "external_observations" in MeihuaInterpretationOptions.model_fields
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "111111", "moving_line": 6},
        external_observations=[{"manifestation": "soil", "label": "虚构新模型探针"}],
    )
    assert (
        out["interpretation"]["external_omens"]["observations"][0]["qualification"]
        == "substantive_generation"
    )
