"""Import order cannot change a public Feng Shui contract's identity."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import fatebridge


@pytest.mark.parametrize("hash_seed", ["0", "1"])
def test_public_contracts_are_stable_across_import_orders(hash_seed):
    source = str(Path(fatebridge.__file__).resolve().parent.parent)
    env = {**os.environ, "PYTHONPATH": source, "PYTHONHASHSEED": hash_seed}
    script = """
import json
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.core.schema_cache import model_schema
result = {}
for spec in CATALOG:
    if spec.family == 'fengshui':
        schema = spec.output_model.model_json_schema()
        result[spec.key] = {
            'north_reference_enum': schema['$defs']['HouseChart']['properties']['north_reference']['anyOf'][0]['enum'],
            'input_schema': model_schema(spec.request_model), 'output_schema': model_schema(spec.output_model), 'required_output_fields': spec.required_output_fields,
        }
print(json.dumps(result, sort_keys=True))
"""
    orders = [
        "",
        "from fatebridge.core.fengshui.calendar import solar_term_resolution\nfrom fatebridge.services import fengshui\n",
    ]
    results = []
    for imports in orders:
        process = subprocess.run(
            [sys.executable, "-c", imports + script],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        results.append(json.loads(process.stdout))
    assert len(results[0]) == 8
    assert results[0] == results[1]
    assert all(
        value["north_reference_enum"] == ["magnetic", "true"]
        for value in results[0].values()
    )
