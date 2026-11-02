"""Development-only source fault bootstrap; never a production dispatch hook."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root)]
from fatebridge.core.astro import native_execution  # noqa: E402

native_execution._WORKER_ACTIVE = True
from scripts.check_human_design_natal_sources import regression_checks  # noqa: E402

print(json.dumps(regression_checks(), ensure_ascii=False))
