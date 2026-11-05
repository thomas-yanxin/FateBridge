"""Poem groups and source-fault classification on actual local transports."""

import asyncio
import json

import pytest

from fatebridge.core import heluo_poems as hp
from tests.support.transports import SPECS, business, call_cli, native
from tests.support.transports import rest as shared_rest

rest = shared_rest
CASES = [
    ("2000-01-21", "05:33:00", 0, 1, 2),
    ("2000-01-31", "01:33:00", 0, 2, 3),
    ("2000-01-13", "09:33:00", 0, 3, 2),
    ("2000-01-01", "11:33:00", 1, 4, 2),
    ("2000-01-31", "09:33:00", 1, 5, 3),
    ("2000-01-02", "13:33:00", 1, 6, 3),
]


@pytest.fixture(autouse=True)
def native_source_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


def run_three(spec, payload, fields, rest, tmp_path, capsys):
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            {
                **payload,
                "fields": fields,
                "strict_fields": True,
                "response_char_limit": 0,
            },
        )
    )
    return response, code, cli, mcp


@pytest.mark.parametrize("date,time,phase,line,count", CASES)
def test_six_poem_groups_have_same_text_and_distinct_source_on_rest_mcp_cli(
    date, time, phase, line, count, rest, tmp_path, capsys
):
    payload = dict(
        date=date, time=time, zone="+08:00", gender="男", use_true_solar_time=False
    )
    fields = [
        "input_normalized",
        "chart",
        "numerology_evidence.selected_texts",
        "numerology_evidence.poem_collation",
        "numerology_evidence.commentary_collation",
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
        assert (s["hexagram"], s["line"]) == ("乾為天", line)
        assert len(t["poem_sections"]) == count
        assert all(x["applicability"] is None for x in t["poem_sections"])
        assert "象曰" not in t["shige"] and t["shige"] in output["snapshot_text"]
        assert "未择用" in output["snapshot_text"]
        assert (
            p["poem_source_pdf_sha256"]
            == e["poem_collation"]["source_pdf_sha256"]
            != p["commentary_source_pdf_sha256"]
        )
        assert (
            e["poem_collation"]["collated_line_poem_groups"],
            e["poem_collation"]["collated_individual_poems"],
        ) == (48, 117)
        trace = next(
            r["facts"]
            for r in e["rule_trace"]
            if r["rule_id"] == "heluo_selected_line_collation_v1"
        )
        assert trace["poem_content_sha256"] == p["poem_content_sha256"]
        assert trace["selections"][phase]["poem_count"] == count
        assert trace["selections"][phase]["poem_pdf_pages"] == p["poem_pdf_pages"]


@pytest.mark.parametrize("fault", ["forged_text", "commentary_source_substitution"])
def test_poem_source_fault_is_503_before_narrow_projection_across_transports(
    fault, rest, tmp_path, capsys, monkeypatch
):
    data = json.loads(hp.COLLATION_PATH.read_bytes())
    if fault == "forged_text":
        data["entries"][0]["poems"][0]["text"] = "非空伪文"
    else:
        data["source_pdf_sha256"] = (
            "fd203ebcd4dc355dbb1ddd3cbee0a72051a2ca6f7a3e0945027690aac8de0b0c"
        )
    path = tmp_path / "fault.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    hp._collation.cache_clear()
    try:
        monkeypatch.setattr(hp, "COLLATION_PATH", path)
        payload = dict(
            date="2000-01-22",
            time="21:33:00",
            zone="+08:00",
            gender="男",
            use_true_solar_time=False,
        )
        response, code, cli, mcp = run_three(
            SPECS["heluo"], payload, ["analysis_type"], rest, tmp_path, capsys
        )
        assert response.status_code == 503 and code != 0 and mcp.is_error
        for output in [response.json(), cli, mcp.structured_content]:
            text = json.dumps(output)
            assert (
                "invalid_heluo_poem_collation" in text
                and "numerology_source_inconsistent" in text
            )
        # Canping does not depend on the separate Heluo poem source.
        response, code, cli, mcp = run_three(
            SPECS["canping"], payload, ["analysis_type"], rest, tmp_path, capsys
        )
        assert response.status_code == 200 and code == 0 and not mcp.is_error
    finally:
        hp._collation.cache_clear()
