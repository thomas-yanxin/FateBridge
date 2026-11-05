"""Independent TZif inputs and expected physical UTC labels."""

import json
from pathlib import Path


def load():
    return json.loads(
        (
            Path(__file__).parents[1] / "data/meihua/unspecified_clock_inputs.json"
        ).read_bytes()
    )
