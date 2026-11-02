"""Frozen source notes must accompany the text actually used in every view."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.heluo import build_snapshot_text, yao_text
from fatebridge.core.heluo_timing import selected_timing_snapshot
from fatebridge.core.local_techniques.heluo import build_heluo_result
from tests.heluo_ben22_revision_reference import (
    rebind_r96_business22,
    rebind_r96_render_row,
)
from tests.heluo_current_source_reference import (
    advance_current_business,
    advance_current_render_row,
)
from tests.heluo_shike_bi_revision_reference import (
    rebind_r92_business22,
    rebind_r92_render_row,
)
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

F = Path(__file__).parent / "fixtures/heluo_reading_delivery_v1"
ORACLE = json.loads((F / "source-delivery-oracle.json").read_bytes())
from tests.heluo_bo23_revision_reference import (
    rebind_r101_business,
    rebind_r101_render_row,
)

ROWS = [
    advance_current_render_row(
        rebind_r101_render_row(rebind_r96_render_row(rebind_r92_render_row(row)))
    )
    for row in ORACLE["rows"]
]
LOOKUP = {(r["gua"], r["line"]): r for r in ROWS}
CASES = json.loads((F / "cases.json").read_bytes())["cases"]
PROTOCOL = json.loads((F / "protocol.json").read_bytes())
rest = shared_rest


@pytest.fixture(autouse=True)
def source_model(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def literal_notes(row):
    notes = [f"爻辞读文说明：{n}" for n in row["header_notes"]]
    notes += [f"注文读文说明：{n}" for n in row["commentary_notes"]]
    for p in row["poem_notes"]:
        notes += [f"第{p['index']}首诗读文说明：{n}" for n in p["notes"]]
    if row["supplement_scope"]:
        notes.append("后续五首复核范围：" + row["supplement_scope"])
    for p in row["supplement_notes"]:
        notes += [f"第{p['index']}首后续复核：{n}" for n in p["notes"]]
    return notes


def assert_notes(block, row, *, isolated=True):
    assert all(note in block for note in literal_notes(row))
    if isolated:
        assert block.count("后续五首复核范围：") == bool(row["supplement_scope"])


def assert_full_snapshot_notes(snapshot, result):
    selections = [
        LOOKUP[(s["hexagram"], s["line"])]
        for s in result["numerology_evidence"]["selected_texts"]
    ] + [LOOKUP[(s["gua"], s["pos"])] for s in result["heluo_timing"]["selected_texts"]]
    for row in selections:
        assert_notes(snapshot, row, isolated=False)
    assert snapshot.count("后续五首复核范围：") == sum(
        bool(row["supplement_scope"]) for row in selections
    )


def test_delivery_reference_is_frozen_before_code_and_keeps_missing_query_controls():
    for name, digest in PROTOCOL["fixture_files"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    assert PROTOCOL["before_any_runtime_edits"] is True
    assert len(ROWS) == 384 and len(LOOKUP) == 384
    cases = json.loads((F / "cases.json").read_bytes())
    assert cases["found_coordinates"] == 16
    assert cases["missing_coordinates"] == [["annual", 1], ["annual", 3]]
    assert len(CASES) == 22
    assert PROTOCOL["requirements"]["new_source_glyph_decisions"] == 0
    assert PROTOCOL["requirements"]["new_real_world_outcomes"] == 0
    migration = json.loads(
        (F / "historical-snapshot-migration-final.json").read_bytes()
    )
    assert migration["source_row"] == {"gua": "風地觀", "line": 1}
    assert migration["added_literal_note_lines"] == literal_notes(LOOKUP[("風地觀", 1)])
    assert migration["after_block"] == migration["before_block"] + "\n" + "\n".join(
        migration["added_literal_note_lines"]
    )


@pytest.mark.parametrize("kind", ["body", "already_modified"])
def test_historical_snapshot_bridge_rejects_unreviewed_or_repeated_changes(kind):
    from tests.test_heluo_tool import READING_DELIVERY, _r90_reading_notes

    before = READING_DELIVERY["before_block"]
    assert _r90_reading_notes(before) == READING_DELIVERY["after_block"]
    bad = (
        before.replace("注文：", "注文：篡改", 1)
        if kind == "body"
        else READING_DELIVERY["after_block"]
    )
    with pytest.raises(AssertionError):
        _r90_reading_notes(bad)


@pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r['gua']}{r['line']}")
def test_all384_lines_keep_literal_notes_in_both_natal_and_three_timing_views(row):
    # These charts are renderer inputs, not newly calculated birth examples.
    control = {"name": "天雷無妄", "lines": [1, 0, 0, 1, 1, 1], "yuan": 1}
    target = {"name": row["gua"], "lines": row["lines"], "yuan": row["line"]}
    for phase, label in [("xian", "先天"), ("hou", "后天")]:
        chart = {
            "tian": 0,
            "di": 0,
            "tianGua": "",
            "diGua": "",
            "xian": copy.deepcopy(control),
            "hou": copy.deepcopy(control),
        }
        chart[phase] = target
        text = build_snapshot_text(chart, None, None)
        block = text.split(f"[{label}·{row['gua']} 元堂爻辞]\n", 1)[1].split(
            "\n\n[", 1
        )[0]
        assert row["poem_source_label"] + "：" in block
        assert_notes(block, row)
    for scope, key, label, index_key in [
        ("annual", "selected_annual", "年标签", "year_label"),
        ("month_ordinal", "selected_month", "月序", "month_index"),
        ("day_template_ordinal", "selected_day", "日定式序", "day_index"),
    ]:
        timing = {
            "selected_annual": {
                "gua": control["name"],
                "lines": control["lines"],
                "pos": 1,
                "year_label": 2000,
            },
            "selected_month": None,
            "selected_day": None,
        }
        timing[key] = {
            "gua": row["gua"],
            "lines": row["lines"],
            "pos": row["line"],
            index_key: 1,
        }
        timing["selected_texts"] = [
            {
                "scope": scope,
                "gua": row["gua"],
                "pos": row["line"],
                "heluo_commentary": yao_text(row["gua"], row["line"]),
            }
        ]
        before = copy.deepcopy(timing)
        text = selected_timing_snapshot(timing)
        block = text.split(f"{label}1：", 1)[1]
        assert_notes(block, row)
        assert timing == before
        assert "尚未桥接实际日期" in text


@pytest.mark.parametrize(
    "index,case",
    list(enumerate(CASES)),
    ids=lambda v: str(v) if isinstance(v, int) else v["kind"],
)
def test_full_business_results_change_only_snapshot_text(index, case, tmp_path):
    before = json.loads((F / "before22" / f"{index:02d}.json").read_bytes())
    # R90 stays frozen; advance only R92's sealed source fields, keeping all math exact.
    before = rebind_r101_business(
        rebind_r96_business22(rebind_r92_business22(before, index), index),
        "business22",
        index,
    )
    before = advance_current_business(before, "business22", index)
    actual = build_heluo_result(**case["payload"])
    (tmp_path / "full-business-after.json").write_text(
        json.dumps(actual, ensure_ascii=False, indent=2) + "\n"
    )
    assert {k: v for k, v in actual.items() if k != "snapshot_text"} == {
        k: v for k, v in before.items() if k != "snapshot_text"
    }
    assert_full_snapshot_notes(actual["snapshot_text"], actual)


@pytest.mark.parametrize(
    "index,case",
    list(enumerate(CASES)),
    ids=lambda v: str(v) if isinstance(v, int) else v["kind"],
)
def test_actual_three_adapters_keep_new_qualifications_with_snapshot_only_projection(
    index, case, rest, tmp_path, capsys
):
    response, code, cli, mcp = run_three(
        SPECS["heluo"], case["payload"], ["snapshot_text"], rest, tmp_path, capsys
    )
    outputs = [response.json(), cli, mcp.structured_content]
    (tmp_path / "raw-three-adapters.json").write_text(
        json.dumps(
            {
                "HTTP_status": response.status_code,
                "CLI_exit": code,
                "MCP_is_error": mcp.is_error,
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    before = json.loads((F / "before22" / f"{index:02d}.json").read_bytes())
    for output in outputs:
        assert_full_snapshot_notes(output["snapshot_text"], before)
