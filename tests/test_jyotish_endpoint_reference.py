"""Seal the independent failure corpus without counting production as correct."""

import ast
import hashlib
import json
from pathlib import Path

import pytest

from scripts.audit_jyotish_endpoints import (
    EXTENDED_REFERENCE_SHA256,
    REFERENCE_SHA256,
    validate_reference,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/jyotish-endpoint-reference.json"


def test_endpoint_reference_is_independent_and_complete():
    reference = validate_reference(REFERENCE)
    assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == REFERENCE_SHA256
    assert len(reference["expected_directions"]) == 8
    assert len(reference["birth_inputs"]) == 2
    assert reference["position_line_arcsec"] == 2.0
    assert reference["protocol"]["not_blind"]
    tree = ast.parse((ROOT / "scripts/gen_jyotish_endpoint_reference.py").read_text())
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        assert not any(
            name == "swisseph" or name.startswith("fatebridge") for name in names
        )


def test_extended_reference_has_correct_physical_targets():
    path = REFERENCE.with_name("jyotish-endpoint-extended-reference.json")
    reference = validate_reference(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == EXTENDED_REFERENCE_SHA256
    assert len(reference["expected_directions"]) == 6
    targets = {"Moon": "'301'", "Jupiter": "'5'", "Saturn": "'6'"}
    assert all(
        r["parameters"]["COMMAND"] == targets[r["body"]] for r in reference["requests"]
    )
    assert reference["not_blind"]
    tree = ast.parse(
        (ROOT / "scripts/gen_jyotish_endpoint_extended_reference.py").read_text()
    )
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        assert not any(
            name == "swisseph" or name.startswith("fatebridge") for name in names
        )


@pytest.mark.parametrize("changed", ["missing_case", "raw_response", "threshold"])
def test_altered_endpoint_reference_cannot_replace_original_failures(changed, tmp_path):
    reference = json.loads(REFERENCE.read_text())
    if changed == "missing_case":
        reference["expected_directions"].pop()
    elif changed == "raw_response":
        reference["requests"][0]["raw_response_utf8"] += " "
    else:
        reference["position_line_arcsec"] = 10.0
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(reference))
    with pytest.raises(ValueError, match="Frozen endpoint reference changed"):
        validate_reference(path)
