"""Actual local REST/MCP/CLI selection of the twelve new source groups."""

import json

import pytest

from fatebridge.core import heluo_poems as hp
from tests.evaluation.test_agentic_nested_outputs import SPECS, business
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.numerology.test_heluo_poem_transports import run_three

rest = shared_rest
CASES = [
    ("2000-01-28", "05:33:00", 0, "坤為地", 1, 2),
    ("2000-01-09", "21:33:00", 1, "坤為地", 2, 2),
    ("2000-01-18", "23:33:00", 1, "坤為地", 3, 3),
    ("2000-01-05", "01:33:00", 1, "坤為地", 4, 3),
    ("2000-01-04", "13:33:00", 0, "坤為地", 5, 2),
    ("2000-01-01", "21:33:00", 0, "坤為地", 6, 3),
    ("2000-01-01", "07:33:00", 1, "水雷屯", 1, 2),
    ("2000-02-10", "11:33:00", 0, "水雷屯", 2, 3),
    ("2000-02-11", "03:33:00", 1, "水雷屯", 3, 2),
    ("2000-01-08", "15:33:00", 0, "水雷屯", 4, 1),
    ("2000-01-02", "21:33:00", 0, "水雷屯", 5, 2),
    ("2000-01-17", "17:33:00", 0, "水雷屯", 6, 2),
]


@pytest.fixture(autouse=True)
def native_source_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("date,time,phase,gua,line,count", CASES)
def test_twelve_group_selections_and_clock_sources_match_all_three_transports(
    date, time, phase, gua, line, count, rest, tmp_path, capsys
):
    payload = dict(
        date=date, time=time, zone="+08:00", gender="男", use_true_solar_time=False
    )
    fields = [
        "input_normalized",
        "numerology_evidence.birth_clock",
        "numerology_evidence.selected_texts",
        "numerology_evidence.poem_collation",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    response, code, cli, mcp = run_three(
        SPECS["heluo"], payload, fields, rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        SPECS["heluo"].output_model.model_validate(output)
        e = output["numerology_evidence"]
        s = e["selected_texts"][phase]
        t = s["text"]
        p = t["text_provenance"]
        assert (s["hexagram"], s["line"]) == (gua, line)
        assert len(t["poem_sections"]) == count
        assert all(x["applicability"] is None for x in t["poem_sections"])
        assert (
            t["shige"] in output["snapshot_text"]
            and "未择用" in output["snapshot_text"]
        )
        assert e["birth_clock"]["calculation_wall_clock"] == date + " " + time
        assert e["birth_clock"]["mode"] == "civil"
        assert p["poem_content_sha256"] == hp.CONTENT_SHA256
        assert (
            e["poem_collation"]["collated_line_poem_groups"],
            e["poem_collation"]["collated_individual_poems"],
        ) == (48, 117)
        trace = next(
            r["facts"]
            for r in e["rule_trace"]
            if r["rule_id"] == "heluo_selected_line_collation_v1"
        )
        assert trace["selections"][phase]["poem_count"] == count
        if gua == "水雷屯" and line == 1:
            assert t["poem_sections"][0]["text"].startswith("不當進步且盤桓")
        if gua == "水雷屯" and line == 4:
            assert (
                p["poem_heading_text"] == "屯卦四爻訣"
                and t["poem_sections"][0]["printed_label"] is None
            )


def test_erasing_source_negation_is_source_fault_before_projection(
    rest, tmp_path, capsys, monkeypatch
):
    data = json.loads(hp.COLLATION_PATH.read_bytes())
    entry = next(
        e for e in data["entries"] if (e["hexagram"], e["line"]) == ("水雷屯", 1)
    )
    entry["poems"][0]["text"] = entry["poems"][0]["text"].removeprefix("不當")
    path = tmp_path / "negation-fault.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    hp._collation.cache_clear()
    try:
        monkeypatch.setattr(hp, "COLLATION_PATH", path)
        payload = dict(
            date="2000-01-01",
            time="07:33:00",
            zone="+08:00",
            gender="男",
            use_true_solar_time=False,
        )
        response, code, cli, mcp = run_three(
            SPECS["heluo"], payload, ["analysis_type"], rest, tmp_path, capsys
        )
        assert response.status_code == 503 and code != 0 and mcp.is_error
        for output in [response.json(), cli, mcp.structured_content]:
            assert "invalid_heluo_poem_collation" in json.dumps(output)
    finally:
        hp._collation.cache_clear()
