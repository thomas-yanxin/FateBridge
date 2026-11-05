"""Source scope and conditional references survive real REST, MCP and CLI."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core import heluo_texts as ht
from tests.support.heluo_source_facts import HEADER_COUNT, PENDING_COUNT
from tests.support.transports import SPECS, business, call_cli, native
from tests.support.transports import rest as shared_rest

rest = shared_rest


@pytest.fixture(autouse=True)
def native_source_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("texts_only", [False, True])
@pytest.mark.parametrize(
    "date,time,phase,gua,line,excerpt",
    [
        ("2000-01-22", "21:33:00", 1, "地水師", 3, "如與命相合者變升三爻"),
        ("2000-01-04", "01:33:00", 1, "水地比", 2, "言發於真見"),
        ("2000-01-12", "09:33:00", 0, "地水師", 5, "職業日繁"),
        ("2000-01-09", "21:33:00", 0, "水地比", 5, "罟網之徒"),
    ],
)
def test_shibi_selection_and_source_scope_agree_on_three_surfaces(
    texts_only, date, time, phase, gua, line, excerpt, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = dict(
        date=date, time=time, zone="+08:00", gender="男", use_true_solar_time=False
    )
    fields = (
        ["numerology_evidence.selected_texts"]
        if texts_only
        else [
            "chart",
            "judge.month_affinity",
            "judge.najia",
            "numerology_evidence.selected_texts",
            "numerology_evidence.commentary_collation",
            "numerology_evidence.rule_trace",
            "snapshot_text",
        ]
    )
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
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        spec.output_model.model_validate(output)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        e = output["numerology_evidence"]
        selected = e["selected_texts"][phase]
        t = selected["text"]
        assert (selected["hexagram"], selected["line"]) == (gua, line)
        assert excerpt in t["detail"]
        assert (
            t["text_provenance"]["commentary_content_sha256"]
            == ht.COMMENTARY_CONTENT_SHA256
        )
        assert all(s["applicability"] is None for s in t["commentary_sections"])
        assert t["commentary_branch_selection"]["selected_section_ids"] == []
        if gua == "地水師" and line == 3:
            ref = t["commentary_cross_references"][0]
            assert ref["target_hexagram"] == "地風升" and ref["target_line"] == 3
            assert (
                ref["applicability"] is None
                and ref["automatic_application"] is False
                and ref["replaces_chart"] is False
            )
            if not texts_only:
                assert output["chart"]["hou"]["name"] == "地水師"
                assert "适用未定，不替代后天卦" in output["snapshot_text"]
        if gua == "水地比" and line == 2:
            assert (
                "戊戌" not in t["detail"]
                and "戊戌" in t["text_provenance"]["inherited_detail"]
            )
            if not texts_only:
                clause = output["judge"]["month_affinity"]["phases"][phase][
                    "natal_najia_clause"
                ]
                assert clause["source_pdf_page"] == 136 and clause["match"] is None
        if not texts_only:
            assert (
                e["commentary_collation"]["collated_line_commentaries"],
                e["commentary_collation"]["pending_line_commentaries"],
            ) == (HEADER_COUNT, PENDING_COUNT)
            trace = next(
                row["facts"]
                for row in e["rule_trace"]
                if row["rule_id"] == "heluo_selected_line_collation_v1"
            )
            assert (
                trace["commentary_content_sha256"]
                == t["text_provenance"]["commentary_content_sha256"]
            )
            assert t["detail"] in output["snapshot_text"]


def test_new_shi3_body_tamper_is_rejected_before_narrow_projection(
    rest, tmp_path, capsys, monkeypatch
):
    spec = SPECS["heluo"]
    payload = dict(
        date="2000-01-22",
        time="21:33:00",
        zone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    data = json.loads(ht.COMMENTARY_PATH.read_bytes())
    entry = next(
        e for e in data["entries"] if (e["hexagram"], e["line"]) == ("地水師", 3)
    )
    entry["sections"][-1]["text"] = entry["sections"][-1]["text"].replace(
        "變升三爻", "變升二爻"
    )
    replacement = tmp_path / "changed-source.json"
    replacement.write_text(json.dumps(data, ensure_ascii=False))
    real_digest = hashlib.sha256(ht.COMMENTARY_PATH.read_bytes()).hexdigest()
    ht._commentary_collation.cache_clear()
    try:
        monkeypatch.setattr(ht, "COMMENTARY_PATH", replacement)
        fields = ["analysis_type"]
        response = rest.post(
            spec.rest_path,
            json=payload,
            params=[("fields", f) for f in fields] + [("strict_fields", "true")],
        )
        code, cli = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=["--fields", *fields, "--strict-fields", "true"],
        )
        mcp = asyncio.run(
            native(spec, {**payload, "fields": fields, "strict_fields": True})
        )
        assert response.status_code == 503 and code != 0 and mcp.is_error
        for output in (response.json(), cli, mcp.structured_content):
            assert "invalid_heluo_commentary_collation" in json.dumps(output)
    finally:
        ht._commentary_collation.cache_clear()
    assert (
        hashlib.sha256(
            Path("src/fatebridge/data/heluo/commentary-collation-v1.json").read_bytes()
        ).hexdigest()
        == real_digest
    )
