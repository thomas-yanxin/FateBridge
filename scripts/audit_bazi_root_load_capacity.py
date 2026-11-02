"""Replay the immutable first root-load development runner."""

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
    path = FIXTURE / "development-first-runner.py.txt"
    binding = FIXTURE / "pre-development.json"
    checksum = hashlib.sha256(binding.read_bytes()).hexdigest()
    if checksum != binding.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen development binding changed")
    expected = json.loads(binding.read_text())["runner_sha256"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Frozen development runner changed")
    loader = importlib.machinery.SourceFileLoader("_root_load_development", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Cannot load frozen development runner")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.__dict__["ROOT"] = ROOT
    module.__dict__["FIXTURE"] = FIXTURE
    return module


def audit(stage: str) -> dict[str, Any]:
    return cast(dict[str, Any], frozen_runner().__dict__["audit"](stage))


def main() -> None:
    frozen_runner().__dict__["main"]()


if __name__ == "__main__":
    main()
