"""Cold imports keep nested schemas valid and domain engines lazy."""

import subprocess
import sys


def test_domain_requests_build_nested_schemas():
    code = """
from fatebridge.core.requests.divination import SixYaoRequest
from fatebridge.core.requests.astrology import AstroRelativeRequest
sixyao = SixYaoRequest.model_validate({'date': '2028-01-01', 'time': '00:00:00',
    'lines': [{'value': 1, 'change': True}] + [{'value': 0, 'change': False}] * 5})
assert len(sixyao.lines) == 6
assert sixyao.lines[0].value == 1 and sixyao.lines[0].change
assert 'SixYaoLineRequest' in SixYaoRequest.model_json_schema()['$defs']
assert 'AstroRelativePartyRequest' in AstroRelativeRequest.model_json_schema()['$defs']
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_catalog_cold_import_does_not_load_domain_engines():
    code = """
import sys
from fatebridge.services.tool_catalog import CATALOG
assert len({spec.key for spec in CATALOG}) == len(CATALOG)
for module in ('kerykeion', 'fatebridge.services.bazi',
               'fatebridge.services.astrology', 'fatebridge.services.western_timing'):
    assert module not in sys.modules, module
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
