"""Frozen twelve-record literary requirements and bounded source behavior."""

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import gua_lines, lines_to_gua, yao_text
from fatebridge.core.numerology_knowledge import _catalogue
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import NumerologySourceError

W = Path(__file__).parent / "fixtures/heluo_fu24_wuwang25_v1"
LITERAL = json.loads((W / "reviewed-literals-v1.json").read_bytes())
from tests.heluo_source_facts import CATALOGUE_VERSION, HEADER_COUNT, PENDING_COUNT


def test_reading_retractions_do_not_gain_independent_reader_or_repair_credit():
    assert LITERAL["new_independent_readers"] == 0
    assert (
        len(
            [
                x
                for x in LITERAL["postcomparison_amendments"]
                if x["inherited_was_correct"] is True
            ]
        )
        == 3
    )
    assert all(
        x["inherited_error_credit"] is False
        for x in LITERAL["postcomparison_amendments"]
    )


@pytest.mark.parametrize(
    "ref", LITERAL["conditional_references"], ids=lambda r: str(r["source_line"])
)
def test_printed_hexagram_without_printed_target_line_keeps_parent_and_leaf_conditions(
    ref,
):
    text = yao_text("地雷復", ref["source_line"])
    rows = text.get("commentary_cross_references", [])
    assert len(rows) == 1
    actual = rows[0]
    for field in [
        "source_quote",
        "source_context_text",
        "condition_text",
        "target_hexagram",
        "target_line",
        "target_line_source_status",
        "target_quote",
    ]:
        assert actual[field] == ref[field], field
    assert actual["source_section_id"] == ref["section_id"]
    assert actual["source_condition_label"] == ref["condition_label"]
    assert actual["target_line"] is actual["applicability"] is None
    assert actual["automatic_application"] is actual["replaces_chart"] is False
    before = gua_lines("坤", "震")
    after = before[:]
    after[ref["source_line"] - 1] = 1 - after[ref["source_line"] - 1]
    assert actual["source_lines"] == before and actual["target_lines"] == after
    assert lines_to_gua(after)["name"] == ref["target_hexagram"]
    summary = ht.text_status_snapshot(text)
    assert ref["condition_text"] in summary
    assert "未指定目标爻" in summary and "不替代正式后天卦" in summary


def test_three_qualified_glyphs_stay_visible_and_current_counts_are_not_accuracy_scores():
    for gua, line in [("地雷復", 1), ("地雷復", 4), ("地雷復", 5)]:
        assert "字形未决" in ht.text_status_snapshot(yao_text(gua, line))
    assert (
        ht.collation_summary()["collated_line_headers"],
        ht.collation_summary()["pending_line_headers"],
    ) == (HEADER_COUNT, PENDING_COUNT)
    assert (
        ht.commentary_collation_summary()["collated_line_commentaries"],
        ht.commentary_collation_summary()["pending_line_commentaries"],
    ) == (HEADER_COUNT, PENDING_COUNT)
    assert _catalogue()["version"] == CATALOGUE_VERSION


@pytest.mark.parametrize(
    "entry", LITERAL["entries"], ids=lambda e: f"knowledge-{e['hexagram']}-{e['line']}"
)
def test_knowledge_summary_keeps_the_actual_reading_notes_and_unknown_conditions(entry):
    out = calculate_knowledge_read(
        domain="heluo", key=f"{entry['hexagram']}:{entry['line']}"
    )
    assert out["reference_details"]["record"]["detail"] == "".join(
        s["text"] for s in entry["sections"]
    )
    assert out["reference_details"]["personal_applicability_assessed"] is False
    for note in entry["reading_notes"]:
        assert note in "\n".join(out["lines"]) and note in out["snapshot_text"]
    assert "None" not in out["snapshot_text"]


@pytest.mark.parametrize("fault", ["body", "parent", "uncertainty", "reference_line"])
def test_content_and_explicit_qualification_mutations_cannot_retain_reviewed_identity(
    fault, monkeypatch, tmp_path
):
    data = json.loads(ht.COMMENTARY_PATH.read_bytes())
    entry = next(
        e for e in data["entries"] if e["hexagram"] == "地雷復" and e["line"] == 3
    )
    if fault == "body":
        entry["sections"][3]["text"] = entry["sections"][3]["text"].replace(
            "名可成", "咎可成"
        )
    elif fault == "parent":
        entry["sections"][3]["condition_label"] = "叶者"
    elif fault == "uncertainty":
        entry = next(
            e for e in data["entries"] if e["hexagram"] == "地雷復" and e["line"] == 5
        )
        entry["review_status"] = "independently_certified"
        entry["reading_notes"] = []
    else:
        entry["sections"][3]["text"] = entry["sections"][3]["text"].replace(
            "變明夷", "變明夷六三"
        )
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(ht, "COMMENTARY_PATH", path)
    ht._commentary_collation.cache_clear()
    try:
        with pytest.raises(NumerologySourceError):
            ht._commentary_collation()
    finally:
        ht._commentary_collation.cache_clear()


from fatebridge.services.tool_catalog import CATALOG
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

rest = shared_rest


@pytest.fixture(autouse=True)
def source_calendar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
