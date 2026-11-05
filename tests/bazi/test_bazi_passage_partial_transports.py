"""Eleven entries retain full same-run passage facts under the fixed budget."""

import asyncio
import json
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.output_classical_passage import ClassicalPassage
from fatebridge.core.output_passage_relations import PassageRelationContext
from tests.support.bazi_transport_reader import (
    cli_payload,
    file_payload,
    native_with_manifest,
    save_json,
    verify_identity,
)
from tests.support.transports import SPECS, business, call_cli
from tests.support.transports import rest as _rest_fixture

rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[2]
PUBLIC = json.loads((ROOT / "tests/data/bazi/root-public-inputs.json").read_text())


def get(payload, path):
    for name in path.split("."):
        payload = payload[name]
    return payload


@pytest.mark.parametrize("case", PUBLIC, ids=lambda c: c["id"])
def test_full_passage_and_context_same_run_across_actual_transports(
    case, rest, tmp_path, capsys
):
    spec = SPECS[case["tool"]]
    views = suggested_fields(spec, view="passage_relations")
    fields = [views[0].removesuffix(".source"), views[-1]]
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 8192,
    }
    result, manifest = asyncio.run(
        native_with_manifest(spec, case["arguments"], case["as_of"], flags, tmp_path)
    )
    assert not result.is_error
    payloads = [file_payload(result.structured_content, manifest, tmp_path, "mcp")]
    code, local = call_cli(
        spec,
        case["arguments"],
        tmp_path,
        capsys,
        flags=[
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "8192",
            "--fields",
            *fields,
        ],
    )
    save_json(tmp_path / "cli-original-response.json", local)
    assert code == 0
    payloads.append(cli_payload(local, tmp_path, capsys))
    if spec.rest_path:
        response = rest.post(spec.rest_path, json=case["arguments"], params=flags)
        value = response.json()
        save_json(tmp_path / "rest-original-response.json", value)
        assert response.status_code == 200
        rest_manifest = None
        if value.get("result_delivery"):
            response = rest.get("/api/results/" + value["result_delivery"]["result_id"])
            save_json(tmp_path / "rest-manifest.json", response.json())
            assert response.status_code == 200
            rest_manifest = response.json()
            verify_identity(
                value["result_delivery"], value["run_metadata"], rest_manifest
            )
        payloads.append(file_payload(value, rest_manifest, tmp_path, "rest"))
    for payload in payloads:
        spec.output_model.model_validate(payload)
        passage, context = (get(payload, f) for f in fields)
        ClassicalPassage.model_validate(passage)
        PassageRelationContext.model_validate(context)
        assert passage["summary"]["effective_passage"] == "not_adjudicated"
        assert context["effective_passage"] == "not_adjudicated"
    assert all(business(p) == business(payloads[0]) for p in payloads)
