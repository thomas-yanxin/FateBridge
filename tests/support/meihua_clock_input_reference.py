"""Manual component truth, frozen before the clock provenance implementation."""

import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).parents[1] / "fixtures/meihua_clock_input_v1"
MANIFEST_SHA256 = "b5bb013453cb68e7b211b81aee0419bec763ab5a69b69d5e9c04085570efef30"


def cases():
    raw = (FOLDER / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    manifest = json.loads(raw)
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest
    result = json.loads((FOLDER / "cases16.json").read_bytes())
    assert len(result) == 16
    return result


def assert_clock_input(result, case, provenance):
    clock = result["meihua"]["calendar_policy"]["civil_clock_resolution"]
    receipt = clock["input_components"]
    for actual, expected in [
        ("supplied_components", "expected_supplied_components"),
        ("omitted_components", "expected_omitted_components"),
        ("calculation_defaults", "expected_calculation_defaults"),
        ("nominal_civil_datetime", "expected_nominal_local_datetime"),
        ("uncertainty_interval", "expected_uncertainty_interval"),
        ("calendar_stability", "expected_stability_assessment"),
        ("observed_precision_certified", "expected_precision_certificate"),
    ]:
        assert type(receipt[actual]) is type(case[expected])
        assert receipt[actual] == case[expected]
    assert receipt["provenance"] == provenance
    assert clock["local_datetime"] == case["expected_nominal_local_datetime"]
    assert result["summary"] == result["interpretation"]["comprehensive_judgement"]
    assert result["summary"].count(receipt["statement"]) == int(
        case["expected_summary_default_notice"]
    )
    assert result["meihua"]["rule_trace"][-1]["result"] == clock
    assert (
        result["interpretation"]["evidence_scope"]["clock_input"]["calendar_stability"]
        == "not_assessed"
    )
    return receipt
