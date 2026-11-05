"""Current complete receipts for verifier tests; these are not sky references."""

import json
import os
import tempfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

from fatebridge.application.execution import execute_tool
from fatebridge.services.tool_catalog import CATALOG

SPEC = next((spec for spec in CATALOG if spec.key == "human_design"))


def complete_run(**request):
    return execute_tool(SPEC, SPEC.request_model(**request))


@lru_cache(maxsize=8)
def _semantic_sources(group):
    root = Path(__file__).resolve().parents[2]
    declarations = json.loads(
        (root / "tests/data/human_design/semantic-inputs.json").read_text()
    )[group]
    results = {}
    for key, case in declarations.items():
        with tempfile.TemporaryDirectory() as empty:
            path = (
                root / "tests/data/human_design/jpl"
                if case["backend"] == "jpl"
                else Path(empty) if case["backend"] == "moshier" else root / "ephe"
            )
            with patch.dict(os.environ, {"SE_EPHE_PATH": str(path)}):
                if case["backend"] == "jpl":
                    os.environ["FATEBRIDGE_JPL_FILE"] = "human-design-de441-j2000.eph"
                else:
                    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
                results[key] = complete_run(**case["request"])
    return results


def semantic_sources(group):
    return deepcopy(_semantic_sources(group))
