"""Six complete source parents, bounded edges and actual transport delivery."""

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.heluo import yao_text
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.services.tool_catalog import CATALOG
from tests.evaluation.test_agentic_nested_outputs import SPECS, business
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.numerology.test_heluo_poem_transports import run_three

rest = shared_rest


@pytest.fixture(autouse=True)
def actual_calendar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def test_annual_dayu_reference_keeps_whole_parent_and_does_not_invent_a_line():
    t = yao_text("山火賁", 2)
    r = t["commentary_cross_references"][0]
    assert r["target_hexagram"] == "山天大畜" and r["target_line"] is None
    assert r["target_line_source_status"] == "not_printed"
    assert (
        r["source_section_id"] == "annual" and r["source_condition_label"] == "歲運逢之"
    )
    assert r["source_context_text"] == t["commentary_sections"][-1]["text"]
    assert (
        r["applicability"] is None
        and r["automatic_application"] is r["replaces_chart"] is False
    )
    assert r["target_lines"] == [1, 1, 1, 0, 0, 1]
    out = calculate_knowledge_read(domain="heluo", key="山火賁:2")
    notes = [s for s in out["lines"] if s.startswith("有条件引文说明：")]
    assert len(notes) == 1 and r["source_context_text"] in notes[0]
    assert "None" not in notes[0] and "不替代正式卦盘" in notes[0]
