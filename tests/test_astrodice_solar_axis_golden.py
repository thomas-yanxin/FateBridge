"""Controlled metadata migration must preserve every other golden leaf."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
RUN = ROOT / "docs/validation/astrodice-solar-axis-run-2026-10-28"


def test_only_six_declared_metadata_paths_changed_in_the_golden():
    name = "tests/golden/snapshots/api_astro_relative.json"
    receipt = json.loads((RUN / "causal-followups-before-change.json").read_text())[
        name
    ]
    before_path = ROOT / receipt["before_copy"]
    assert (
        hashlib.sha256(before_path.read_bytes()).hexdigest() == receipt["before_sha256"]
    )
    before = json.loads(before_path.read_text())
    # Preserve the actual after-edition of this six-leaf historical migration.
    # Current numerical goldens have a separate Linux acceptance gate.
    after_path = (
        ROOT / "tests/fixtures/architecture_refactor_v1/solar-axis-golden-after.json"
    )
    assert (
        hashlib.sha256(after_path.read_bytes()).hexdigest()
        == "e1ce57da22ba58f76342c40535cf3abba1fd1f835bf02f0b2a6709f3fd56b634"
    )
    after = json.loads(after_path.read_text())
    migration = json.loads((RUN / "golden-causal-leaf-migration.json").read_text())
    allowed = {row["path"]: row for row in migration["changes"]}
    visited = set()

    def compare(a, b, path):
        if path in allowed:
            row = allowed[path]
            assert a == row["before"] and b == row["after"]
            assert path.rsplit(".", 1)[-1] in {
                "method_id",
                "scope",
                "source_model_regularity",
            }
            visited.add(path)
        elif isinstance(a, dict):
            added = set(b) - set(a)
            assert set(a) <= set(b)
            for key in added:
                child = path + "." + key
                assert key == "source_model_regularity" and child in allowed
                compare(None, b[key], child)
            for key in a:
                compare(a[key], b[key], path + "." + key)
        elif isinstance(a, list):
            assert isinstance(b, list) and len(a) == len(b)
            for i, (x, y) in enumerate(zip(a, b)):
                compare(x, y, path + f"[{i}]")
        else:
            assert type(a) is type(b) and a == b, path

    compare(before, after, "$")
    assert visited == set(allowed) and len(visited) == 6
    assert migration["linux_byte_replay_performed"] is False
