"""Printed absent-label and reference line distinctions on actual transports."""

import asyncio
import hashlib
import json

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core import heluo_texts as ht
from tests.heluo_current_source_reference import HEADER_COUNT, PENDING_COUNT
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as shared_rest

rest = shared_rest


@pytest.fixture(autouse=True)
def native_source_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("texts_only", [False, True])
@pytest.mark.parametrize(
    "date,time,phase,gua,line,excerpt",
    [
        ("2000-01-04", "09:33:00", 1, "風天小畜", 1, "數凶者變巽初爻"),
        ("2000-02-01", "03:33:00", 0, "風天小畜", 3, "謀則不從"),
        ("2000-01-10", "19:33:00", 0, "天澤履", 4, "虎符將帥"),
        ("2000-01-13", "17:33:00", 1, "風天小畜", 5, "主同協意"),
    ],
)
def test_xiaochuli_printed_scopes_agree_on_rest_mcp_cli(
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
            "numerology_evidence.selected_texts",
            "numerology_evidence.yaoci_collation",
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
        p = t["text_provenance"]
        assert (selected["hexagram"], selected["line"]) == (gua, line) and excerpt in t[
            "detail"
        ]
        assert (
            p["commentary_content_sha256"] == ht.COMMENTARY_CONTENT_SHA256
            and p["header_content_sha256"] == ht.HEADER_CONTENT_SHA256
        )
        assert all(s["applicability"] is None for s in t["commentary_sections"])
        assert t["commentary_branch_selection"]["selected_section_ids"] == []
        if gua == "風天小畜" and line == 1:
            ref = t["commentary_cross_references"][0]
            assert ref["target_hexagram"] == "巽為風" and ref["target_line"] == 1
            assert (
                ref["applicability"] is None
                and ref["automatic_application"] is ref["replaces_chart"] is False
            )
            if not texts_only:
                assert "不替代后天巽四爻" in output["snapshot_text"]
        elif gua == "風天小畜" and line == 3:
            assert [s["section_id"] for s in t["commentary_sections"]] == [
                "opening",
                "xie",
                "annual",
            ]
            assert t["commentary_branch_selection"][
                "condition_labels_not_separately_printed"
            ] == ["不葉者"]
            assert "不葉者" not in t["detail"]
            if not texts_only:
                assert "未印标签不表示不匹配" in output["snapshot_text"]
        elif gua == "天澤履" and line == 4:
            assert t["yaoci"] == "履虎尾，愬愬終吉。" and p["pdf_page"] == 142
            assert "愬恕" in p["inherited_yaoci"]
        if not texts_only:
            assert (
                e["commentary_collation"]["collated_line_commentaries"],
                e["commentary_collation"]["pending_line_commentaries"],
            ) == (HEADER_COUNT, PENDING_COUNT)
            assert (
                e["yaoci_collation"]["collated_line_headers"],
                e["yaoci_collation"]["pending_line_headers"],
            ) == (HEADER_COUNT, PENDING_COUNT)
            trace = next(
                r["facts"]
                for r in e["rule_trace"]
                if r["rule_id"] == "heluo_selected_line_collation_v1"
            )
            assert (
                trace["header_content_sha256"] == p["header_content_sha256"]
                and trace["commentary_content_sha256"] == p["commentary_content_sha256"]
            )
            assert t["detail"] in output["snapshot_text"]


@pytest.mark.parametrize("layer", ["commentary", "header"])
def test_source_fabrication_or_wrong_header_fails_before_narrow_projection(
    layer, rest, tmp_path, capsys, monkeypatch
):
    spec = SPECS["heluo"]
    payload = dict(
        date="2000-02-01",
        time="03:33:00",
        zone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    attr, loader = (
        ("COMMENTARY_PATH", ht._commentary_collation)
        if layer == "commentary"
        else ("COLLATION_PATH", ht._collation)
    )
    path = getattr(ht, attr)
    raw = path.read_bytes()
    data = json.loads(raw)
    if layer == "commentary":
        e = next(
            e for e in data["entries"] if (e["hexagram"], e["line"]) == ("風天小畜", 3)
        )
        e["sections"].insert(
            2,
            dict(
                section_id="buxie",
                condition_label="不葉者",
                text="不葉者此為補造條件。",
            ),
        )
    else:
        e = next(
            e for e in data["entries"] if (e["hexagram"], e["line"]) == ("天澤履", 4)
        )
        e["yaoci"] = e["yaoci"].replace("愬愬", "愬恕")
    fault = tmp_path / "fault.json"
    fault.write_text(json.dumps(data, ensure_ascii=False))
    loader.cache_clear()
    try:
        monkeypatch.setattr(ht, attr, fault)
        response = rest.post(
            spec.rest_path,
            json=payload,
            params=[("fields", "analysis_type"), ("strict_fields", "true")],
        )
        code, cli = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=["--fields", "analysis_type", "--strict-fields", "true"],
        )
        mcp = asyncio.run(
            native(
                spec, {**payload, "fields": ["analysis_type"], "strict_fields": True}
            )
        )
        assert response.status_code == 503 and code != 0 and mcp.is_error
        reason = (
            "invalid_heluo_commentary_collation"
            if layer == "commentary"
            else "invalid_heluo_header_collation"
        )
        for output in (response.json(), cli, mcp.structured_content):
            assert reason in json.dumps(output)
    finally:
        loader.cache_clear()
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(raw).digest()
