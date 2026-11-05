"""Keep rejected strength witnesses, whole-source failures and old cards visible."""

import asyncio

import pytest

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

KEYS = ("暖局与用神", "日元强弱与性情措辞", "根位与有效接引")

rest = _shared_rest


@pytest.mark.parametrize("key", KEYS)
def test_new_source_conditions_survive_rest_native_mcp_and_cli(
    key, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "category": "classical_force_semantics", "key": key}
    options = {"include_snapshot_text": True, "response_char_limit": 0}
    http = rest.post(spec.rest_path, json=payload, params=options)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "true", "--response-char-limit", "0"],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    value = http.json()
    curation = value["provenance"]["entry_curation"]
    assert (
        curation["source_refs"][0]["source_sha256"]
        == "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert (
        curation["review_status"]
        == "single_developer_source_reading_external_review_pending"
    )
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    assert curation["source_refs"][0]["edition"] in value["snapshot_text"]
    if key == "日元强弱与性情措辞":
        assert len(value["tips"]) == 8
        assert curation["method_id"] == "dtcw1947_body_vocabulary_semantics_v3"
        assert curation["entry_revision"] == 3
        assert len(curation["source_relation_binding"]["rows"]) == 20
    else:
        assert len(value["tips"]) == 5
        assert curation["entry_revision"] == 1
    if key == "暖局与用神":
        assert "用神必在酉金" in value["snapshot_text"]
        assert "用神不在丙火而在辰土" in value["snapshot_text"]
