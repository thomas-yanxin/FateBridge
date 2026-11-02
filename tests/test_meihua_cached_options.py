"""An archived request module and current lazy services reproduce the live fault."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures/meihua_cached_options_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]
SCRIPT = r"""
import importlib,importlib.util,json,sys
from pathlib import Path
fixture=Path(sys.argv[1]);
if len(sys.argv)>2:sys.path.insert(0,sys.argv[2])
importlib.import_module('fatebridge.core.requests')
name='fatebridge.core.requests.meihua';spec=importlib.util.spec_from_file_location(name,fixture/'v18-request-meihua.py');module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
parent=sys.modules['fatebridge.core.requests'];setattr(parent,'meihua',module)
assert 'external_observations' not in module.MeihuaInterpretationOptions.model_fields
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.services.divination import calculate_meihua_analysis
results=[]
for c in json.loads((fixture/'cases.json').read_text())['cases']:
 args={'casting':{'method':'existing','hexagram_code':'111111','moving_line':6},'interpretation_topic':'wealth'} if c['tool']=='cast' else {'analysis_year':2026,'analysis_month':10,'analysis_day':22,'analysis_hour':12,'analysis_timezone':'Asia/Shanghai','interpretation_topic':'wealth'}
 if c.get('explicit_none'):args['external_observations']=None
 if c.get('external_provided'):args['external_observations']=[{'manifestation':'soil','label':'虚构工程旧模型校验'}]
 f=calculate_meihua_cast if c['tool']=='cast' else calculate_meihua_analysis
 out=f(**args);results.append({'id':c['id'],'success':'error' not in out,'error_code':out.get('error_code'),'error':out.get('error'),'external_omens':out.get('interpretation',{}).get('external_omens')})
import fatebridge,inspect
print(json.dumps({'old_model_has_new_field':False,'loaded_package_file':fatebridge.__file__,'service_files':[inspect.getsourcefile(inspect.unwrap(calculate_meihua_cast)),inspect.getsourcefile(inspect.unwrap(calculate_meihua_analysis))],'results':results}))
"""


@pytest.fixture(scope="module")
def stale_results():
    proc = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(FIXTURE)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.splitlines()[-1])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_archived_cached_model_and_current_optional_default_calls(case, stale_results):
    out = next(r for r in stale_results["results"] if r["id"] == case["id"])
    assert out["success"] is case["expected_success"], out
    if not case["expected_success"]:
        assert out["error_code"] == case["expected_error_code"]
    else:
        assert out["external_omens"] is None


def test_archived_request_bytes_are_the_frozen_v18_module():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    for name, digest in m["files"].items():
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
