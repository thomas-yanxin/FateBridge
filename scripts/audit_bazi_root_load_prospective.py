"""Replay the immutable first prospective runner through a typed local loader.

The study runner retains its original bytes, including the dynamic module setup.
Only workspace paths are supplied; the runner verifies its own frozen digest and
all candidate, annotation, dependency and failed-launch bindings before replay.
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_load_capacity_v2"


def frozen_runner() -> ModuleType:
    path = FIXTURE / "prospective-r2-runner.py.txt"
    binding = FIXTURE / "pre-prospective-r2.json"
    checksum = hashlib.sha256(binding.read_bytes()).hexdigest()
    if checksum != binding.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen prospective binding changed")
    expected = json.loads(binding.read_text())["runner_sha256"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Frozen prospective runner changed")
    loader = importlib.machinery.SourceFileLoader("_root_load_prospective", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Cannot load frozen prospective runner")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.__dict__["ROOT"] = ROOT
    module.__dict__["FIXTURE"] = FIXTURE
    return module


def audit() -> dict[str, Any]:
    return cast(dict[str, Any], frozen_runner().__dict__["audit"]())


def main() -> None:
    frozen_runner().__dict__["main"]()


if __name__ == "__main__":
    main()
