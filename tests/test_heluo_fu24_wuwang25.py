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
from tests.heluo_current_source_reference import (
    CATALOGUE_VERSION,
    HEADER_COUNT,
    PENDING_COUNT,
    REFERENCE,
)

BEFORE = {key: edge["before"] for key, edge in REFERENCE["records"].items()}


def test_first_draft_and_retractions_are_frozen_without_independent_reader_credit():
    assert (
        hashlib.sha256((W / "source-first-draft.json").read_bytes()).hexdigest()
        == "1200eefccd57185a90265ac806df3460e819ae3aa37bbcc6d486ebae5bcb6eb7"
    )
    seal = json.loads((W / "first-draft-seal.json").read_bytes())
    for name, digest in seal["files"].items():
        path = W / name
        raw = (
            path.read_bytes()
            if path.exists()
            else gzip.decompress((W / "reproduction" / (name + ".gz")).read_bytes())
        )
        assert hashlib.sha256(raw).hexdigest() == digest, name
    assert seal["before_inherited_target_words_visible"]
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
    "entry", LITERAL["entries"], ids=lambda e: f"{e['hexagram']}-{e['line']}"
)
def test_actual_header_and_all_parented_commentary_words_match_the_selected_page(entry):
    actual = yao_text(entry["hexagram"], entry["line"])
    assert actual["yaoci"] == entry["yaoci"]
    assert actual["detail"] == "".join(s["text"] for s in entry["sections"])
    assert actual["commentary_sections"] == [
        dict(s, applicability=None) for s in entry["sections"]
    ]
    assert actual["text_provenance"]["commentary_pdf_pages"] == entry["pdf_pages"]
    assert (
        actual["text_provenance"]["commentary_reading_notes"] == entry["reading_notes"]
    )
    assert actual["commentary_branch_selection"]["selected_section_ids"] == []
    before = BEFORE[f"{entry['hexagram']}:{entry['line']}"]
    assert actual["shige"] == before["shige"] and actual["verdict"] == before["verdict"]


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


@pytest.mark.parametrize(
    "key,field,needle",
    [
        ("地雷復:1", "yaoci", "无祗悔"),
        ("地雷復:1", "detail", "善專其心"),
        ("地雷復:4", "detail", "為兵師"),
        ("地雷復:5", "detail", "涵養熟"),
        ("地雷復:6", "yaoci", "用行師"),
        ("地雷復:6", "detail", "取擢之辱"),
        ("天雷無妄:1", "detail", "重德清心"),
        ("天雷無妄:2", "yaoci", "不菑畬"),
        ("天雷無妄:2", "detail", "粱稻熟"),
        ("天雷無妄:3", "detail", "羊財"),
        ("天雷無妄:5", "detail", "不勞而理"),
        ("天雷無妄:6", "detail", "不諳於事"),
    ],
)
def test_explicit_inherited_differences_do_not_disappear_into_punctuation_only_changes(
    key, field, needle
):
    assert needle not in BEFORE[key][field]
    gua, line = key.rsplit(":", 1)
    assert needle in yao_text(gua, int(line))[field]


def test_all384_poems_and_verdicts_and_other372_complete_literal_objects_stay_exact():
    for key, before in BEFORE.items():
        gua, line = key.rsplit(":", 1)
        actual = yao_text(gua, int(line))
        assert (
            actual["shige"] == before["shige"]
            and actual["verdict"] == before["verdict"]
        )
        if gua not in ["地雷復", "天雷無妄"]:
            from tests.heluo_fu24_wuwang25_revision_reference import (
                REFERENCE as R102_REFERENCE,
            )

            historical = R102_REFERENCE["records"][key]["after"]
            assert {k: v for k, v in historical.items() if k != "text_provenance"} == {
                k: v for k, v in before.items() if k != "text_provenance"
            }, key
            expected = REFERENCE["records"][key]["after"]
            assert actual == expected, key


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
CASES = json.loads((W / "case-search/cases.json").read_bytes())["cases"]


@pytest.fixture(autouse=True)
def source_calendar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["label"])
def test_actual_three_adapters_keep_source_words_and_bounded_references(
    case, rest, tmp_path, capsys
):
    fields = [
        "chart",
        "four_pillars",
        "calendar_context",
        "numerology_evidence.selected_texts",
        "numerology_evidence.commentary_collation",
        "heluo_timing.selected_texts",
        "snapshot_text",
    ]
    response, code, cli, mcp = run_three(
        SPECS["heluo"], case["payload"], fields, rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    expected = REFERENCE["records"][f"{case['hexagram']}:{case['line']}"]["after"]
    for output in outputs:
        selected = next(
            s["text"]
            for s in output["numerology_evidence"]["selected_texts"]
            if s["hexagram"] == case["hexagram"] and s["line"] == case["line"]
        )
        assert selected == expected
        assert (
            selected["yaoci"] in output["snapshot_text"]
            and selected["detail"] in output["snapshot_text"]
        )
        for ref in selected.get("commentary_cross_references", []):
            assert ref["target_line"] is ref["applicability"] is None
            assert ref["automatic_application"] is ref["replaces_chart"] is False
            assert ref["condition_text"] in ht.text_status_snapshot(selected)
        for note in selected["text_provenance"]["commentary_reading_notes"]:
            assert note in output["snapshot_text"]


@pytest.mark.parametrize(
    "entry", LITERAL["entries"], ids=lambda e: f"knowledge-{e['hexagram']}-{e['line']}"
)
def test_actual_three_knowledge_adapters_preserve_nulls_and_show_source_qualification(
    entry, rest, tmp_path, capsys
):
    spec = next(s for s in CATALOG if s.key == "knowledge_read")
    key = f"{entry['hexagram']}:{entry['line']}"
    response, code, cli, mcp = run_three(
        spec,
        {"domain": "heluo", "key": key},
        ["reference_details", "provenance", "lines", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert (
            output["reference_details"]["record"] == REFERENCE["records"][key]["after"]
        )
        assert output["reference_details"]["personal_applicability_assessed"] is False
        assert "修订：None" not in output["snapshot_text"]
        assert any(
            r["source_revision"] is None for r in output["provenance"]["source_records"]
        )
        assert "修订：未提供；" in output["snapshot_text"]
        for note in entry["reading_notes"]:
            assert note in output["snapshot_text"] and note in "\n".join(
                output["lines"]
            )
