"""Independent firdaria vectors used by engine and transport tests."""

import json
from pathlib import Path

VECTORS = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "firdaria-reference.json").read_text(
        encoding="utf-8"
    )
)
