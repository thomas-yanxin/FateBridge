"""Pinned Gu18 commentary and Xu5 poem witnesses, with unresolved readings kept."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import heluo_poems as hp
from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, yao_text
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.services.knowledge import calculate_knowledge_read
from tests.evaluation.test_agentic_nested_outputs import SPECS, business
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.numerology.test_heluo_poem_transports import run_three
from tests.support.heluo_source_facts import HEADER_COUNT, PENDING_COUNT

F = Path(__file__).parents[1] / "fixtures/heluo_gu18_xu5_v1"
READINGS = json.loads((F / "accepted-readings.json").read_bytes())
CASES = json.loads(
    (Path(__file__).parents[1] / "data/heluo/gu_xu_routes.json").read_text()
)
rest = shared_rest


@pytest.fixture(autouse=True)
def independent_source_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    for f in [ht._collation, ht._commentary_collation, hp._collation]:
        f.cache_clear()
    yield
    for f in [ht._collation, ht._commentary_collation, hp._collation]:
        f.cache_clear()


def test_source_first_drafts_and_all_withdrawals_remain_hashed():
    for name in [
        "first-draft-freeze.json",
        "source-only-verified-freeze.json",
        "source-reading-freeze.json",
        "late-source-freeze.json",
    ]:
        record = json.loads((F / name).read_bytes())
        for path, digest in record["files"].items():
            assert hashlib.sha256((F / path).read_bytes()).hexdigest() == digest
    first = json.loads((F / "first-draft-freeze.json").read_bytes())
    final = json.loads((F / "source-reading-freeze.json").read_bytes())
    assert first["inherited_target_text_exposed"] is False
    assert first["individual_poems"] == 16
    assert final["source_only_draft_amendments"] == 6
    assert final["postcomparison_amendments"] == 2
    assert final[
        "inherited_correct_readings_restored_not_counted_as_product_fixes"
    ] == ["Gu1夫", "Gu3歷"]
    assert final["new_independent_readers"] == 0


def test_current_source_coverage_and_pending_groups_remain_explicit():
    assert (
        ht.collation_summary()["collated_line_headers"],
        ht.collation_summary()["pending_line_headers"],
    ) == (HEADER_COUNT, PENDING_COUNT)
    assert (
        ht.commentary_collation_summary()["collated_line_commentaries"],
        ht.commentary_collation_summary()["pending_line_commentaries"],
    ) == (HEADER_COUNT, PENDING_COUNT)
    p = hp.collation_summary()
    assert (
        p["collated_line_poem_groups"],
        p["pending_line_poem_groups"],
        p["collated_individual_poems"],
        p["total_individual_poems"],
    ) == (48, 336, 117, None)


@pytest.mark.parametrize(
    "entry", READINGS["commentaries"], ids=lambda e: str(e["line"])
)
def test_complete_gu_commentary_keeps_source_words_and_parent_conditions(entry):
    result = yao_text("山風蠱", entry["line"])
    expected = [dict(s, applicability=None) for s in entry["sections"]]
    assert result["yaoci"] == entry["yaoci"]
    assert result["commentary_sections"] == expected
    assert result["detail"] == "".join(s["text"] for s in expected)
    assert result["commentary_branch_selection"]["selected_section_ids"] == []
    old = _tiaowen()["山風蠱"]["yao"][str(entry["line"])]
    assert (result["shige"], result["verdict"]) == (old["shige"], old["verdict"])
    assert all(
        n in result["text_provenance"]["commentary_reading_notes"]
        for n in entry["reading_notes"]
    )
    if entry["line"] == 2:
        assert (
            "glyph_choice_unresolved"
            in result["text_provenance"]["commentary_review_status"]
        )
        assert "女命勤儉持家" in expected[-1]["text"]
    if entry["line"] == 4:
        assert "不能設施" in expected[1]["text"]
        assert "一變為鼎九四" in expected[-1]["text"]


@pytest.mark.parametrize("entry", READINGS["poems"], ids=lambda e: str(e["line"]))
def test_all16_xu_poems_keep_individual_order_clause_boundaries_and_uncertainty(entry):
    result = yao_text("水天需", entry["line"])
    expected = deepcopy(entry["poems"])
    for p in expected:
        p["applicability"] = None
        if entry["line"] == 5 and p["index"] in [1, 2]:
            p["review_status"] = (
                "single_reader_native_pixel_collation; glyph_choice_unresolved; independent_second_review_pending"
            )
    assert result["poem_sections"] == expected
    assert result["shige"] == "\n".join(p["text"] for p in expected)
    assert result["poem_selection"]["selected_poem_indices"] == []
    assert result["poem_selection"]["automatic_selection"] is False
    assert "unverified" in result["inherited_xiang_reference"]["status"]
    assert (
        result["text_provenance"]["poem_heading_pdf_page"] == entry["heading_pdf_page"]
    )
    assert result["text_provenance"]["poem_pdf_pages"] == entry["pdf_pages"]
    old = _tiaowen()["水天需"]["yao"][str(entry["line"])]
    assert result["text_provenance"]["inherited_shige"] == old["shige"]
    assert result["verdict"] == old["verdict"]


def test_gu4_annual_ding4_reference_does_not_replace_actual_natal_phase():
    text = yao_text("山風蠱", 4)
    (ref,) = text["commentary_cross_references"]
    assert ref["source_lines"] == [0, 1, 1, 0, 0, 1]
    assert ref["target_lines"] == [0, 1, 1, 1, 0, 1]
    assert ref["target_hexagram"] == "火風鼎" and ref["target_line"] == 4
    assert ref["target_line_source_status"] == "printed"
    assert ref["target_quote"] is None
    assert ref["source_section_id"] == "annual"
    assert ref["source_condition_label"] == ref["condition_text"] == "歲運逢之"
    assert ref["source_quote"] == "一變為鼎九四。"
    assert ref["pdf_pages"] == [162]
    assert ref["applicability"] is None
    assert ref["automatic_application"] is ref["replaces_chart"] is False
    case = next(c for c in CASES if c["hexagram"] == "山風蠱" and c["line"] == 4)
    output = build_heluo_result(**case["payload"])
    assert case["phase"] == 1
    assert output["chart"]["xian"]["name"] == "風火家人"
    assert output["chart"]["xian"]["yuan"] == 1
    assert output["chart"]["hou"]["name"] == "山風蠱"
    assert output["chart"]["hou"]["yuan"] == 4
    selected = output["numerology_evidence"]["selected_texts"][1]
    assert selected["text"]["commentary_cross_references"] == [ref]


@pytest.mark.parametrize("key", ["山風蠱:2", "山風蠱:4", "水天需:4", "水天需:5"])
def test_reference_summary_preserves_new_source_notes_and_condition_scope(key):
    result = calculate_knowledge_read(domain="heluo", key=key)
    record = result["reference_details"]["record"]
    notes = record["text_provenance"].get("commentary_reading_notes", [])
    notes += [
        n for p in record.get("poem_sections", []) for n in p.get("reading_notes", [])
    ]
    for note in notes:
        assert note in "\n".join(result["lines"])
        assert note in result["snapshot_text"]
    if key == "山風蠱:4":
        assert "一變為鼎九四" in "\n".join(result["lines"])
        assert "不替代正式卦盘" in "\n".join(result["lines"])


@pytest.mark.parametrize(
    "kind",
    [
        "header_word",
        "commentary_uncertain_glyph",
        "commentary_parent",
        "poem_word",
        "poem_uncertainty_note",
        "poem_boundary",
    ],
)
def test_actual_temporary_source_tampering_is_rejected_before_projection(
    kind, monkeypatch, tmp_path
):
    if kind.startswith("header"):
        module, attr = ht, "COLLATION_PATH"
    elif kind.startswith("commentary"):
        module, attr = ht, "COMMENTARY_PATH"
    else:
        module, attr = hp, "COLLATION_PATH"
    data = json.loads(getattr(module, attr).read_bytes())
    gua = "山風蠱" if module is ht else "水天需"
    entry = next(
        e
        for e in data["entries"]
        if e["hexagram"] == gua
        and e["line"]
        == (
            2
            if kind == "commentary_uncertain_glyph"
            else (
                4
                if kind == "commentary_parent"
                else 5 if kind == "poem_uncertainty_note" else 1
            )
        )
    )
    if kind == "header_word":
        entry["yaoci"] = entry["yaoci"].replace("无", "無")
    elif kind == "commentary_uncertain_glyph":
        entry["sections"][0]["text"] = entry["sections"][0]["text"].replace("祗", "祇")
    elif kind == "commentary_parent":
        entry["sections"][1]["text"], entry["sections"][-1]["text"] = (
            entry["sections"][-1]["text"],
            entry["sections"][1]["text"],
        )
    elif kind == "poem_word":
        entry["poems"][0]["text"] = entry["poems"][0]["text"].replace("兇", "見")
    elif kind == "poem_uncertainty_note":
        entry["poems"][0]["reading_notes"] = []
    else:
        entry["poems"][0]["printed_clauses"][0] += "字"
    p = tmp_path / (kind + ".json")
    p.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(module, attr, p)
    result = execute_tool(
        SPECS["knowledge_read"],
        SPECS["knowledge_read"].request_model.model_validate(
            dict(domain="heluo", key=gua + ":1")
        ),
    )
    assert result["status_code"] == 503 and result["retryable"] is False


@pytest.mark.parametrize(
    "key", ["山風蠱:2", "山風蠱:4", "水天需:2", "水天需:5", "水天需:6"]
)
def test_source_reference_rest_cli_and_mcp_contracts(key, rest, tmp_path, capsys):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        dict(domain="heluo", key=key),
        ["lines", "reference_details", "provenance"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    record = response.json()["reference_details"]["record"]
    assert record["commentary_branch_selection"]["selected_section_ids"] == []
    if key.startswith("水天需"):
        assert record["poem_selection"]["selected_poem_indices"] == []
