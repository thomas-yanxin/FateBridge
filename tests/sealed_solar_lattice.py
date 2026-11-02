"""Replay the original Sun-root producer on the current native host."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.historical_source_identity import HistoricalSources

CLOSURE_SHA256 = "6035cba38dc2f3428dfed301d54c9b5e3eaf79ec442bb35657cb2aa9d045cd31"


def original_lattice_report(root, environment):
    path = (
        root
        / "tests/fixtures/architecture_refactor_v1/solar-lattice-original-closure.json"
    )
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CLOSURE_SHA256
    closure = json.loads(raw)
    originals = HistoricalSources(root)
    with TemporaryDirectory(prefix="fatebridge-original-solar-lattice-") as directory:
        before = Path(directory)
        for relative, digest in closure["modules"].items():
            original = originals.originals[digest]
            assert "src/" + relative in original["paths"]
            data = original["text"].encode()
            assert hashlib.sha256(data).hexdigest() == digest
            destination = before / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        for relative, digest in closure["resources"].items():
            data = (root / "src" / relative).read_bytes()
            assert hashlib.sha256(data).hexdigest() == digest
            destination = before / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        program = """
import json, sys
from pathlib import Path
from scripts.check_human_design_solar_speed_lattice import compare
report = compare()
original = Path(sys.argv[1])
for name, module in sys.modules.copy().items():
    path = getattr(module, '__file__', None)
    if name.startswith('fatebridge') and path:
        assert Path(path).is_relative_to(original), (name, path)
print(json.dumps(report, ensure_ascii=False))
"""
        completed = subprocess.run(
            [sys.executable, "-c", program, str(before)],
            cwd=root,
            env={**environment, "PYTHONPATH": str(before) + os.pathsep + str(root)},
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return json.loads(completed.stdout)
