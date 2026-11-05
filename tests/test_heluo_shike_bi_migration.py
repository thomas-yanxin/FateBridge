"""Frozen reference edges must reject altered facts and repeated migrations."""

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.heluo import yao_text

ROOT = Path(__file__).parents[1]


def test_old_source_conflicts_and_calendar_gate_have_not_been_edited():
    assert (
        yao_text("天水訟", 3)["text_provenance"]["poem_heading_text"]
        == "訟卦三爻訣一首"
    )
    assert len(yao_text("天水訟", 3)["poem_sections"]) == 3
    assert "poem_review_supplement" in yao_text("天水訟", 1)
    assert (
        hashlib.sha256(
            (ROOT / "tests/fixtures/ren_calendar_guard_v1/reference.json").read_bytes()
        ).hexdigest()
        == "067de02c05332c8ec6437c0393a02c1d7ff356b1ce0ed3d04bc3cc912a19d68c"
    )
