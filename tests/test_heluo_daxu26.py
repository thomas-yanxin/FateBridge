"""Frozen Daxu literals, parent conditions, glyph qualifications and source faults."""

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

W = Path(__file__).parent / "data/heluo"
LITERAL = json.loads((W / "reviewed-literals-v1.json").read_bytes())


@pytest.mark.parametrize("e", LITERAL["entries"], ids=lambda e: str(e["line"]))
def test_six_exact_headers_and_24_complete_parents_with_unassessed_applicability(e):
    t = yao_text("山天大畜", e["line"])
    assert t["yaoci"] == e["yaoci"] and t["detail"] == "".join(
        s["text"] for s in e["sections"]
    )
    assert t["commentary_sections"] == [
        dict(s, applicability=None) for s in e["sections"]
    ]
    assert t["text_provenance"]["commentary_pdf_pages"] == e["pdf_pages"]
    assert t["text_provenance"]["commentary_reading_notes"] == e["reading_notes"]
    assert t["commentary_branch_selection"]["selected_section_ids"] == []


@pytest.mark.parametrize(
    "ref", LITERAL["conditional_references"], ids=lambda r: str(r["source_line"])
)
def test_references_preserve_printed_and_unprinted_target_positions_and_source_parents(
    ref,
):
    t = yao_text("山天大畜", ref["source_line"])
    rows = t.get("commentary_cross_references", [])
    assert len(rows) == 1
    row = rows[0]
    for f in [
        "source_quote",
        "source_context_text",
        "condition_text",
        "target_hexagram",
        "target_line",
        "target_line_source_status",
        "target_quote",
    ]:
        assert row[f] == ref[f], f
    assert (
        row["source_section_id"] == ref["section_id"]
        and row["source_condition_label"] == ref["condition_label"]
    )
    assert (
        row["applicability"] is None
        and row["automatic_application"] is row["replaces_chart"] is False
    )
    bits = gua_lines("艮", "乾")
    after = bits[:]
    after[ref["source_line"] - 1] = 1 - after[ref["source_line"] - 1]
    assert (
        row["source_lines"] == bits
        and row["target_lines"] == after
        and lines_to_gua(after)["name"] == ref["target_hexagram"]
    )
    status = ht.text_status_snapshot(t)
    assert ref["condition_label"] in status
    if ref["target_line"] is None:
        assert "未指定目标爻" in status
    else:
        assert "第6爻" in status and ref["condition_label"] == "不叶者"


@pytest.mark.parametrize("line", [1, 3])
def test_tentative_readings_stay_qualified_and_never_gain_repair_or_certification_credit(
    line,
):
    t = yao_text("山天大畜", line)
    assert "字形未决" in ht.text_status_snapshot(t)
    notes = (
        t["text_provenance"]["header_reading_notes"]
        if line == 1
        else t["text_provenance"]["commentary_reading_notes"]
    )
    assert any("未决" in n for n in notes)
    assert LITERAL["authority_certified"] is False


@pytest.mark.parametrize(
    "e", LITERAL["entries"], ids=lambda e: "knowledge-" + str(e["line"])
)
def test_all_knowledge_surfaces_keep_the_real_source_notes_and_unassessed_selection(e):
    out = calculate_knowledge_read(domain="heluo", key=f"山天大畜:{e['line']}")
    assert out["reference_details"]["record"]["detail"] == "".join(
        s["text"] for s in e["sections"]
    )
    assert out["reference_details"]["personal_applicability_assessed"] is False
    for n in e["reading_notes"]:
        assert n in "\n".join(out["lines"]) and n in out["snapshot_text"]
    assert (
        out["reference_details"]["record"]["commentary_branch_selection"][
            "selected_section_ids"
        ]
        == []
    )


def test_dictionary_gloss_is_explicit_editorial_context_not_raw_commentary_or_glyph_proof():
    t = yao_text("山天大畜", 3)
    notes = t["text_provenance"]["commentary_reading_notes"]
    gloss = next(n for n in notes if "编校词义说明" in n)
    assert (
        "非原文" in gloss
        and "不作字形证据" in gloss
        and "太守" in gloss
        and "个人适用性未裁定" in gloss
    )
    assert "https://dict.revised.moe.edu.tw/dictView.jsp?ID=159452" in gloss
    assert "太守" not in t["detail"] and "dict.revised" not in t["detail"]
    assert "glyph_choice_unresolved" in t["text_provenance"]["commentary_review_status"]


@pytest.mark.parametrize("fault", ["body", "parent", "qualification", "position"])
def test_modified_source_or_qualification_cannot_keep_the_bound_identity(
    fault, monkeypatch, tmp_path
):
    data = json.loads(ht.COMMENTARY_PATH.read_bytes())
    e = next(
        (e for e in data["entries"] if (e["hexagram"], e["line"]) == ("山天大畜", 3)),
        None,
    )
    assert e is not None
    if fault == "body":
        e["sections"][2]["text"] = e["sections"][2]["text"].replace("雖與", "難與")
    elif fault == "parent":
        e["sections"][2]["condition_label"] = "叶者"
    elif fault == "qualification":
        e["review_status"] = "independently_certified"
        e["reading_notes"] = []
    else:
        e = next(
            e for e in data["entries"] if (e["hexagram"], e["line"]) == ("山天大畜", 2)
        )
        e["sections"][1]["text"] = e["sections"][1]["text"].replace(
            "變為賁", "變為賁六二"
        )
    p = tmp_path / "changed.json"
    p.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(ht, "COMMENTARY_PATH", p)
    ht._commentary_collation.cache_clear()
    try:
        with pytest.raises(NumerologySourceError):
            ht._commentary_collation()
    finally:
        ht._commentary_collation.cache_clear()


from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.services.tool_catalog import CATALOG
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

rest = shared_rest
CASES = json.loads((W / "daxu_case_inputs.json").read_bytes())["cases"]


@pytest.fixture(autouse=True)
def source_calendar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["line"]))
def test_six_complete_calculations_keep_math_and_the_formal_houtian(case):
    line = case["line"]
    actual = build_heluo_result(**case["payload"])
    assert actual["chart"][case["phase"]]["name"] == "山天大畜"
    assert actual["chart"][case["phase"]]["yuan"] == line
    if line == 6:
        assert (
            actual["chart"]["hou"]["name"] == "天地否"
            and actual["chart"]["hou"]["yuan"] == 3
        )
        ref = actual["numerology_evidence"]["selected_texts"][0]["text"][
            "commentary_cross_references"
        ][0]
        assert (
            ref["target_hexagram"] == "地天泰"
            and ref["target_line"] == 6
            and ref["source_section_id"] == "buxie"
        )


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["line"]))
def test_actual_three_calculation_adapters_keep_selected_source_and_qualifications(
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
    expected = next(e for e in LITERAL["entries"] if e["line"] == case["line"])
    for out in outputs:
        selected = next(
            s["text"]
            for s in out["numerology_evidence"]["selected_texts"]
            if s["hexagram"] == "山天大畜" and s["line"] == case["line"]
        )
        assert (
            selected["yaoci"] == expected["yaoci"]
            and selected["detail"]
            == "".join(row["text"] for row in expected["sections"])
            and selected["yaoci"] in out["snapshot_text"]
            and selected["detail"] in out["snapshot_text"]
        )
        for note in selected["text_provenance"]["commentary_reading_notes"]:
            assert note in out["snapshot_text"]
        for ref in selected.get("commentary_cross_references", []):
            assert (
                ref["applicability"] is None
                and ref["automatic_application"] is ref["replaces_chart"] is False
            )


@pytest.mark.parametrize(
    "e", LITERAL["entries"], ids=lambda e: "knowledge-" + str(e["line"])
)
def test_actual_three_knowledge_adapters_keep_editorial_and_printed_material_distinct(
    e, rest, tmp_path, capsys
):
    spec = next(s for s in CATALOG if s.key == "knowledge_read")
    key = f"山天大畜:{e['line']}"
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
    for out in outputs:
        record = out["reference_details"]["record"]
        assert record["yaoci"] == e["yaoci"]
        assert record["detail"] == "".join(row["text"] for row in e["sections"])
        assert (
            record["text_provenance"]["commentary_reading_notes"] == e["reading_notes"]
        )
        assert out["reference_details"]["personal_applicability_assessed"] is False
        for note in e["reading_notes"]:
            assert note in out["snapshot_text"] and note in "\n".join(out["lines"])
        if e["line"] == 3:
            assert "编校词义说明（非原文，不作字形证据）" in out["snapshot_text"]
