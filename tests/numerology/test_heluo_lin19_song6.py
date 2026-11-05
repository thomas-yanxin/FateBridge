"""Frozen Lin19/Song6 sources keep wording, conditions and unresolved evidence."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import heluo_poems as hp
from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import yao_text
from fatebridge.services.knowledge import calculate_knowledge_read
from tests.support.transports import SPECS

F = Path(__file__).parents[1] / "fixtures/heluo_lin19_song6_v1"
REFERENCE = json.loads((F / "source-adoption-reference.json").read_bytes())
FAULTS = [
    "header_word",
    "commentary_parent",
    "commentary_quote",
    "poem_negation",
    "poem_count_heading",
    "poem_count_deletion",
    "poem_uncertainty_note",
    "poem_clause_boundary",
    "poem_page",
    "poem_order",
]


@pytest.fixture(autouse=True)
def source_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))
    for fn in [ht._collation, ht._commentary_collation, hp._collation]:
        fn.cache_clear()
    yield
    for fn in [ht._collation, ht._commentary_collation, hp._collation]:
        fn.cache_clear()


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def test_first_readings_all_amendments_and_primary_identities_are_preserved():
    freeze = json.loads((F / "source-reading-freeze.json").read_bytes())
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    assert freeze["frozen_before_production_edits"] is True
    assert freeze["frozen_before_inherited_target_text_exposure"] is False
    first = json.loads((F / "source-only-verified-freeze.json").read_bytes())
    assert first["frozen_before_inherited_target_text_exposure"] is True
    assert freeze["original_correct_readings_restored_not_product_fixes"] == [
        "Song2王事",
        "Song3狂謀",
    ]
    assert freeze["unresolved_count"] == 5
    protocol = json.loads((F / "protocol.json").read_bytes())
    for row in protocol["primary_sources"]:
        assert (
            hashlib.sha256(
                (F / "primary" / (row["kind"] + ".pdf")).read_bytes()
            ).hexdigest()
            == row["sha256"]
        )
    assert (
        protocol["primary_sources"][0]["sha256"]
        != protocol["primary_sources"][1]["sha256"]
    )


@pytest.mark.parametrize(
    "expected", REFERENCE["cross_references"], ids=lambda r: str(r["source_line"])
)
def test_lin_references_keep_parent_conditions_and_no_printed_target_line(expected):
    text = yao_text("地澤臨", expected["source_line"])
    assert text["commentary_cross_references"] == [expected]
    assert (
        expected["target_line"] is None
        and expected["target_line_source_status"] == "not_printed"
    )
    assert (
        expected["applicability"] is None and expected["automatic_application"] is False
    )
    assert expected["replaces_chart"] is False
    summary = "\n".join(
        calculate_knowledge_read(
            domain="heluo", key=f"地澤臨:{expected['source_line']}"
        )["lines"]
    )
    assert expected["source_condition_label"] in summary
    assert "原文未印目标爻位" in summary and "不替代正式卦盘" in summary


def test_source_negation_crosspage_tail_and_count_conflict_stay_visible_in_summary():
    second = yao_text("天水訟", 2)
    assert (
        "時間理未明" in second["shige"]
        and "時聞理義明" in second["text_provenance"]["inherited_shige"]
    )
    three = yao_text("天水訟", 3)
    assert three["text_provenance"]["poem_heading_text"] == "訟卦三爻訣一首"
    assert len(three["poem_sections"]) == 3
    summary = "\n".join(
        calculate_knowledge_read(domain="heluo", key="天水訟:3")["lines"]
    )
    assert "原题訟卦三爻訣一首" in summary and "保留三首和原题" in summary
    six = yao_text("天水訟", 6)
    assert six["poem_sections"][1]["pdf_pages"] == [13]
    assert six["shige"].endswith("心戚戚。恍惚兩三頭。")


def corrupt_source(kind, monkeypatch, tmp_path):
    module, attr = (
        (ht, "COLLATION_PATH")
        if kind == "header_word"
        else (
            (ht, "COMMENTARY_PATH")
            if kind.startswith("commentary")
            else (hp, "COLLATION_PATH")
        )
    )
    data = json.loads(getattr(module, attr).read_bytes())
    gua = "地澤臨" if module is ht else "天水訟"
    pos = (
        2
        if kind in {"header_word", "poem_negation"}
        else (
            5
            if kind.startswith("commentary")
            else 4 if kind == "poem_uncertainty_note" else 3
        )
    )
    entry = next(
        e for e in data["entries"] if e["hexagram"] == gua and e["line"] == pos
    )
    if kind == "header_word":
        entry["yaoci"] = entry["yaoci"].replace("无", "無")
    elif kind == "commentary_parent":
        entry["sections"][1], entry["sections"][2] = (
            entry["sections"][2],
            entry["sections"][1],
        )
    elif kind == "commentary_quote":
        entry["sections"][2]["text"] = entry["sections"][2]["text"].replace(
            "節", "歸妹"
        )
    elif kind == "poem_negation":
        entry["poems"][0]["text"] = entry["poems"][0]["text"].replace("未明", "義明")
    elif kind == "poem_count_heading":
        entry["heading_text"] = entry["heading_text"].replace("一首", "三首")
    elif kind == "poem_count_deletion":
        entry["poems"] = entry["poems"][:1]
    elif kind == "poem_uncertainty_note":
        entry["poems"][1]["reading_notes"] = []
    elif kind == "poem_clause_boundary":
        entry["poems"][0]["printed_clauses"][0] += "字"
    elif kind == "poem_page":
        entry["pdf_pages"] = [11]
    elif kind == "poem_order":
        entry["poems"].reverse()
    else:
        raise AssertionError(kind)
    dest = tmp_path / (kind + ".json")
    dest.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(module, attr, dest)
    return gua + ":" + str(pos)


@pytest.mark.parametrize("kind", FAULTS)
def test_changed_words_parents_count_or_uncertainty_are_source503(
    kind, monkeypatch, tmp_path
):
    key = corrupt_source(kind, monkeypatch, tmp_path)
    spec = SPECS["knowledge_read"]
    result = execute_tool(
        spec, spec.request_model.model_validate(dict(domain="heluo", key=key))
    )
    assert result["status_code"] == 503 and result["retryable"] is False
