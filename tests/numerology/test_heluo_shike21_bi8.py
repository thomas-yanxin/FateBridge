"""Source-first literals, boundaries and delivery; no prediction score."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_poems as hp
from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import build_snapshot_text, yao_text
from fatebridge.core.heluo_timing import selected_timing_snapshot
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.services.tool_catalog import CATALOG
from tests.numerology.test_heluo_poem_transports import run_three
from tests.support.transports import business
from tests.support.transports import rest as shared_rest

F = Path(__file__).parents[1] / "fixtures/heluo_shike21_bi8_v1"
L = json.loads((F / "reviewed-literals-v2.json").read_bytes())
rest = shared_rest
ROWS = [(g, i) for g in ("火雷噬嗑", "水地比") for i in range(1, 7)]


@pytest.fixture(autouse=True)
def clear_sources():
    for fn in (ht._collation, ht._commentary_collation, hp._collation):
        fn.cache_clear()
    yield
    for fn in (ht._collation, ht._commentary_collation, hp._collation):
        fn.cache_clear()


def test_frozen_reading_retains_own_errors_and_no_independent_credit():
    freeze = json.loads((F / "reviewed-literal-freeze.json").read_bytes())
    assert freeze["before_producer_edits"] is True
    for n, h in freeze["files"].items():
        assert hashlib.sha256((F / n).read_bytes()).hexdigest() == h
    first = json.loads((F / "first-source-reading.json").read_bytes())
    assert (
        hashlib.sha256((F / "first-source-reading.json").read_bytes()).hexdigest()
        == freeze["first_reading_sha256"]
    )
    assert sum(len(e["poems"]) for e in first["line_poems"]) == 15
    assert sum(len(e["poems"]) for e in L["poem_groups"]) == 16
    a = json.loads((F / "adjudication.json").read_bytes())
    assert a["first_count_15_wrong_corrected_to_16"] is True
    assert len(a["withdrawals"]) == 6 and all(
        e["inherited_already_correct"] for e in a["withdrawals"]
    )
    assert not a["goal_complete"] and not a["independent_review_added"]


def test_later_pixels_override_green_candidate_and_preserve_all_other_literals():
    freeze = json.loads((F / "reviewed-literal-v2-freeze.json").read_bytes())
    assert freeze["before_next_candidate_edit"] is True
    assert freeze["after_first_candidate_exposure_not_blind"] is True
    for n, h in {**freeze["files"], **freeze["pixel_evidence"]}.items():
        assert hashlib.sha256((F / n).read_bytes()).hexdigest() == h
    old = json.loads((F / "reviewed-literals.json").read_bytes())
    assert old["headers"] == L["headers"] and old["commentaries"] == L["commentaries"]
    for before, after in zip(old["poem_groups"], L["poem_groups"], strict=True):
        if before["line"] != 4:
            assert before == after
        else:
            assert before["poems"][1] == after["poems"][1]
            for index in (0, 2):
                assert (
                    before["poems"][index]["text"].replace("无", "無")
                    == after["poems"][index]["text"]
                )
    a = json.loads((F / "adjudication-v2.json").read_bytes())
    assert a["first_candidate_51pass_not_final_acceptance"] is True
    assert all(e["inherited_already_correct"] for e in a["changes"])


@pytest.mark.parametrize("e", L["commentaries"], ids=lambda e: f"shike{e['line']}")
def test_all_complete_commentary_parents_and_headers(e):
    r = yao_text(e["hexagram"], e["line"])
    assert r["yaoci"] == e["yaoci"]
    assert r["detail"] == "".join(s["text"] for s in e["sections"])
    assert r["commentary_sections"] == [
        dict(s, applicability=None) for s in e["sections"]
    ]
    assert r["text_provenance"]["commentary_pdf_pages"] == e["pdf_pages"]
    assert r["text_provenance"]["commentary_reading_notes"] == e["reading_notes"]
    assert r["commentary_branch_selection"]["selected_section_ids"] == []
    assert (
        r["verdict"]
        == json.loads(
            (
                F / "before-source/src/fatebridge/data/heluo/heluoTiaowen.json"
            ).read_bytes()
        )[e["hexagram"]]["yao"][str(e["line"])]["verdict"]
    )


@pytest.mark.parametrize("e", L["poem_groups"], ids=lambda e: f"bi{e['line']}")
def test_all_sixteen_poems_and_exact_page_and_clause_boundaries(e):
    r = yao_text(e["hexagram"], e["line"])
    assert r["shige"] == "\n".join(p["text"] for p in e["poems"])
    assert r["poem_sections"] == [dict(p, applicability=None) for p in e["poems"]]
    assert r["text_provenance"]["poem_heading_text"] == e["heading_text"]
    assert r["text_provenance"]["poem_pdf_pages"] == e["pdf_pages"]
    assert r["poem_selection"]["selected_poem_indices"] == []
    assert r["poem_selection"]["automatic_selection"] is False


@pytest.mark.parametrize("gua,line", ROWS)
def test_reference_summary_preserves_literal_reading_notes(gua, line):
    r = yao_text(gua, line)
    out = calculate_knowledge_read(domain="heluo", key=f"{gua}:{line}")
    assert (
        out.get("error") is None
        and out["reference_details"]["personal_applicability_assessed"] is False
    )
    s = "\n".join(out["lines"])
    notes = r["text_provenance"].get("header_reading_notes", []) + r[
        "text_provenance"
    ].get("commentary_reading_notes", [])
    notes += [n for p in r.get("poem_sections", []) for n in p.get("reading_notes", [])]
    assert all(n in s for n in notes)
    assert out["provenance"]["independent_whole_corpus_review_completed"] is False
    assert out["provenance"]["real_world_efficacy_validated"] is False


@pytest.mark.parametrize("gua,line", ROWS)
def test_literal_notes_survive_both_natal_and_all_three_timing_renderings(gua, line):
    r = yao_text(gua, line)
    lines = [1, 0, 0, 1, 0, 1] if gua == "火雷噬嗑" else [0, 0, 0, 0, 1, 0]
    target = {"name": gua, "lines": lines, "yuan": line}
    controls = {"name": "天雷無妄", "lines": [1, 0, 0, 1, 1, 1], "yuan": 1}
    notes = r["text_provenance"].get("header_reading_notes", []) + r[
        "text_provenance"
    ].get("commentary_reading_notes", [])
    notes += [n for p in r.get("poem_sections", []) for n in p.get("reading_notes", [])]
    for phase in ("xian", "hou"):
        chart = {
            "tian": 0,
            "di": 0,
            "tianGua": "",
            "diGua": "",
            "xian": controls,
            "hou": controls,
        }
        chart[phase] = target
        text = build_snapshot_text(chart, None, None)
        assert all(n in text for n in notes)
        assert r["detail"] in text
    for scope, key in [
        ("annual", "selected_annual"),
        ("month_ordinal", "selected_month"),
        ("day_template_ordinal", "selected_day"),
    ]:
        item = {
            "gua": gua,
            "lines": lines,
            "pos": line,
            "year_label": 2000,
            "month_index": 1,
            "day_index": 1,
        }
        timing = {
            "selected_annual": dict(item),
            "selected_month": None,
            "selected_day": None,
        }
        timing[key] = item
        timing["selected_texts"] = [
            {"scope": scope, "gua": gua, "pos": line, "heluo_commentary": r}
        ]
        text = selected_timing_snapshot(timing)
        assert all(n in text for n in notes)


def test_conditional_crossreferences_do_not_fill_unprinted_target_line_or_replace_chart():
    one = yao_text("火雷噬嗑", 1)["commentary_cross_references"][0]
    six = yao_text("火雷噬嗑", 6)["commentary_cross_references"][0]
    assert one["target_hexagram"] == "火地晉" and one["target_line"] is None
    assert one["target_line_source_status"] == "not_printed"
    assert six["target_hexagram"] == "震為雷" and six["target_line"] == 6
    assert six["target_line_source_status"] == "printed"
    for r, after in [(one, [0, 0, 0, 1, 0, 1]), (six, [1, 0, 0, 1, 0, 0])]:
        assert r["target_lines"] == after
        assert r["source_section_id"] == "xie" and r["source_condition_label"] == "叶者"
        assert r["condition_text"] == "叶者" and r["applicability"] is None
        assert r["automatic_application"] is False and r["replaces_chart"] is False
    assert "常懷憂懼" in yao_text("火雷噬嗑", 6)["commentary_sections"][1]["text"]


@pytest.mark.parametrize("gua,line", ROWS)
def test_actual_local_rest_mcp_cli_reference_parity(gua, line, rest, tmp_path, capsys):
    spec = next(s for s in CATALOG if s.key == "knowledge_read")
    response, code, cli, mcp = run_three(
        spec,
        {"domain": "heluo", "key": f"{gua}:{line}"},
        ["reference_details", "lines", "provenance"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    out = [response.json(), cli, mcp.structured_content]
    assert business(out[0]) == business(out[1]) == business(out[2])
    assert out[0]["reference_details"]["personal_applicability_assessed"] is False
