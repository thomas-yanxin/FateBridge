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

W = Path(__file__).parent / "fixtures/heluo_daxu26_v1"
LITERAL = json.loads((W / "reviewed-literals-v1.json").read_bytes())
R = Path("/Users/thomas/Desktop/FateBridge")
OLD = json.loads(
    (
        R
        / "tests/fixtures/heluo_fu24_wuwang25_v1/migration-reference-v1/reference.json"
    ).read_bytes()
)
BEFORE = {k: e["after"] for k, e in OLD["records"].items()}


def test_seals_precede_runtime_test_edits_and_all_exposures_and_own_errors_remain():
    seal = json.loads((W / "reviewed-literal-freeze-v1.json").read_bytes())
    for n, d in seal["files"].items():
        assert hashlib.sha256((W / n).read_bytes()).hexdigest() == d, n
    assert (
        seal["before_runtime_or_old_test_edits"]
        and seal["all_external_and_root_target_exposures_disclosed"]
    )
    assert LITERAL["new_independent_readers"] == LITERAL["new_real_world_outcomes"] == 0
    assert LITERAL["postcomparison_and_search_exposure_disclosed"]
    exposure = json.loads((W / "external-target-word-exposure.json").read_bytes())
    assert exposure["occurred_after_source_only_review_v2_sealed"]
    assert all(
        not r.get("inherited_repair_credit", False)
        for r in LITERAL["postcomparison_adjudications"]
    )


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
    assert (
        t["shige"] == BEFORE[f"山天大畜:{e['line']}"]["shige"]
        and t["verdict"] == BEFORE[f"山天大畜:{e['line']}"]["verdict"]
    )


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


@pytest.mark.parametrize(
    "line,field,source,old",
    [
        (2, "yaoci", "輿說輹", "輿脫輹"),
        (2, "detail", "時上之用", "待上之用"),
        (2, "detail", "掛冠致仕", "掛冠致任"),
        (3, "yaoci", "日閑輿衞", "曰閑輿衛"),
        (3, "detail", "雖與君子合志", "難與君子合志"),
        (3, "detail", "知己相助", "知已相助"),
        (5, "detail", "小小規模", "小小規摸"),
    ],
)
def test_frozen_meaning_and_literal_changes_are_not_hidden_as_punctuation(
    line, field, source, old
):
    assert old in BEFORE[f"山天大畜:{line}"][field]
    t = yao_text("山天大畜", line)
    assert source in t[field] and old not in t[field]


def test_old150_entries_and_other378_records_and_every_poem_and_verdict_remain_exact():
    h = ht._collation()
    c = ht._commentary_collation()
    for name, data in [
        ("yaoci-collation-v1.json", h),
        ("commentary-collation-v1.json", c),
    ]:
        old = json.loads(
            gzip.decompress(
                (
                    W
                    / "physical-source-successor/before/src/fatebridge/data/heluo"
                    / (name + ".gz")
                ).read_bytes()
            )
        )
        assert (
            len(old["entries"]) == 150
            and data["entries"][:150] == old["entries"]
            and len(data["entries"]) == 156
        )
    meta = {
        "corpus_id": h["corpus_id"],
        "header_content_sha256": h["_content_sha256"],
        "transcription_policy": h["transcription_policy"],
        "commentary_corpus_id": c["corpus_id"],
        "commentary_sha256": c["_loaded_sha256"],
        "commentary_content_sha256": c["_content_sha256"],
        "commentary_transcription_policy": c["transcription_policy"],
    }
    for key, before in BEFORE.items():
        gua, line = key.rsplit(":", 1)
        actual = yao_text(gua, int(line))
        assert (
            actual["shige"] == before["shige"]
            and actual["verdict"] == before["verdict"]
        )
        if gua != "山天大畜":
            expected = copy.deepcopy(before)
            for f, value in meta.items():
                if f in expected["text_provenance"]:
                    expected["text_provenance"][f] = value
            assert actual == expected, key
    assert _catalogue()["version"] == 15


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
CASES = json.loads((W / "case-search/cases.json").read_bytes())["cases"]
PHYSICAL = json.loads((W / "physical-transition-v1/reference.json").read_bytes())
AFTER_BUSINESS = json.loads(
    gzip.decompress((W / "physical-transition-v1/after-business.json.gz").read_bytes())
)


@pytest.fixture(autouse=True)
def source_calendar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["line"]))
def test_six_complete_calculations_keep_math_and_the_formal_houtian(case):
    line = case["line"]
    before = json.loads((W / f"case-search/before-{case['label']}.json").read_bytes())
    actual = build_heluo_result(**case["payload"])
    assert actual == AFTER_BUSINESS[f"daxu6:{line}"]
    for field in PHYSICAL["math_fields_unchanged"]:
        assert actual[field] == before[field], field
    for field in before["heluo_timing"]:
        if field != "selected_texts":
            assert actual["heluo_timing"][field] == before["heluo_timing"][field], field
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
    expected = PHYSICAL["records"][f"山天大畜:{case['line']}"]["after"]
    for out in outputs:
        selected = next(
            s["text"]
            for s in out["numerology_evidence"]["selected_texts"]
            if s["hexagram"] == "山天大畜" and s["line"] == case["line"]
        )
        assert (
            selected == expected
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
        assert out["reference_details"]["record"] == PHYSICAL["records"][key]["after"]
        assert out["reference_details"]["personal_applicability_assessed"] is False
        for note in e["reading_notes"]:
            assert note in out["snapshot_text"] and note in "\n".join(out["lines"])
        if e["line"] == 3:
            assert "编校词义说明（非原文，不作字形证据）" in out["snapshot_text"]


def test_R102_reference_module_remains_complete_AST_identical_to_its_sealed_original():
    import ast

    import tests.heluo_fu24_wuwang25_revision_reference as previous

    sealed = (
        R
        / "tests/fixtures/heluo_fu24_wuwang25_v1/acceptance-v1/test-support-after/heluo_current_source_reference.py.gz"
    )
    expected = gzip.decompress(sealed.read_bytes()).decode()
    assert ast.dump(
        ast.parse(Path(previous.__file__).read_text()), include_attributes=False
    ) == ast.dump(ast.parse(expected), include_attributes=False)


def test_source_bridge_rejects_an_unbound_intermediate_without_weakening_the_anchor(
    monkeypatch,
):
    import tests.heluo_current_source_reference as current

    assert current.assert_r102_r103_source_bridge()
    original = current.physical_source

    def changed(name, stage="after"):
        value = original(name, stage)
        if name.endswith("yaoci-collation-v1.json") and stage == "before":
            value = copy.deepcopy(value)
            value["entries"][-1]["yaoci"] += "forged"
        return value

    monkeypatch.setattr(current, "physical_source", changed)
    with pytest.raises(AssertionError):
        current.assert_r102_r103_source_bridge()


def test_Daxu_audit_retains_source_uncertainties_and_zero_new_independent_or_outcome_credit():
    from scripts.audit_numerology import daxu26_source_checks

    a = daxu26_source_checks()
    assert a["checks_passed"] and a["failures"] == []
    assert (
        a["new_headers"] == a["new_complete_commentaries"] == 6
        and a["new_parent_sections"] == 24
    )
    assert a["source_pdf_pages"] == [180, 181, 182]
    assert (
        a["independent_reviews_added"]
        == a["new_model_evaluations"]
        == a["new_real_world_outcomes"]
        == 0
    )
    assert a["authority_certified"] is False
