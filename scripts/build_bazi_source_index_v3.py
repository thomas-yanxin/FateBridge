"""Replay the exact frozen v3 generator that produced the retained index.

The initial generator is an execution artifact. Keep its SHA in generated
metadata while allowing this entry point to follow current formatting rules.
No source index, annotation, comparison or numerical threshold is rewritten.
"""

import hashlib
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = (
    ROOT / "tests/fixtures/bazi_source_comparison_v1/index-v3-generator-first.py.txt"
)
EXPECTED_SHA256 = "cef435437511f2b1fc0f61fe43ba5cb330753ef4fca529d54cbffcb0777d5b8d"


def frozen_generator():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == EXPECTED_SHA256
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    return runpy.run_path(str(FROZEN))


def generate():
    return frozen_generator()["generate"]()


def main():
    frozen_generator()["main"]()


if __name__ == "__main__":
    main()
