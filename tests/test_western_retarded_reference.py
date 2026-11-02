"""Seal the independent reduction without mislabelling its shared ephemeris."""

import ast
import json
from pathlib import Path

import pytest

from scripts.audit_western_retarded_model import validate_reference

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "tests/fixtures/western-retarded-model-protocol.json"
REFERENCE = ROOT / "tests/fixtures/western-retarded-model-reference.json"


def test_reduction_reference_is_complete_and_distinct_from_an_independent_ephemeris():
    protocol, reference = validate_reference(PROTOCOL, REFERENCE)
    assert (
        len(reference["rows"]) == len(protocol["cases"]) * len(protocol["frames"]) == 12
    )
    assert reference["candidate_imports"] is False
    assert reference["independent_ephemeris"] is False
    assert reference["independent_model_reduction"] is True
    assert reference["precision_decimal_digits"] == 70
    assert all(len(row["estimates"]) == 2 for row in reference["rows"])
    assert all(
        len(e["raw_samples"]) == 7
        for row in reference["rows"]
        for e in row["estimates"]
    )
    tree = ast.parse(
        (ROOT / "scripts/gen_western_retarded_model_reference.py").read_text()
    )
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(x.name for x in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(x == "fatebridge" or x.startswith("fatebridge.") for x in imports)


@pytest.mark.parametrize("changed", ["protocol", "reference"])
def test_altered_reference_or_coverage_cannot_be_reaccepted(changed, tmp_path):
    protocol, reference = PROTOCOL, REFERENCE
    if changed == "protocol":
        protocol = tmp_path / "protocol.json"
        value = json.loads(PROTOCOL.read_text())
        value["cases"].pop()
        protocol.write_text(json.dumps(value))
    else:
        reference = tmp_path / "reference.json"
        value = json.loads(REFERENCE.read_text())
        value["rows"].pop()
        reference.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="changed"):
        validate_reference(protocol, reference)
