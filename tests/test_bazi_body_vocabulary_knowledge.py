"""Preserve revision2 engineering history; verify current revision3 delivery."""

import asyncio
import json
from pathlib import Path

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = Path("src/fatebridge/data/knowledge/bazi.json")
KEY = "日元强弱与性情措辞"


def read(path):
    return json.loads(path.read_text())


def test_source_voices_and_engineering_boundaries_survive_revision():
    card = read(ROOT / BUNDLE)["categories"]["classical_force_semantics"][KEY]
    curation = card["curation"]
    assert curation["source_refs"][1]["author"] == "李雨田增補"
    assert curation["source_refs"][1]["source_pdf_pages"] == [50]
    assert curation["source_refs"][2]["author"] == "任鐵樵增注（任氏曰）"
    assert curation["source_refs"][2]["source_pdf_pages"] == [175, 176, 177, 178]
    for item in curation["source_refs"]:
        assert (
            item["source_sha256"]
            == "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
        )
    for item in curation["source_refs"][1:]:
        assert item["author"] in curation["citation"]
    partitions = sum(
        (
            curation[k]
            for k in [
                "classical_condition_tip_indexes",
                "implementation_tip_indexes",
                "editorial_tip_indexes",
            ]
        ),
        [],
    )
    assert sorted(partitions) == list(range(8))
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    assert curation["review_status"].endswith("external_review_pending")


def test_revised_vocabulary_is_identical_across_rest_native_mcp_and_cli(
    rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "category": "classical_force_semantics", "key": KEY}
    options = {"include_snapshot_text": True, "response_char_limit": 0}
    http = rest.post(spec.rest_path, json=payload, params=options)
    mcp = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "true", "--response-char-limit", "0"],
    )
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    result = http.json()
    assert business(result) == business(mcp.structured_content) == business(cli)
    curation = result["provenance"]["entry_curation"]
    assert curation["method_id"] == "dtcw1947_body_vocabulary_semantics_v3"
    assert curation["entry_revision"] == 3 and len(result["tips"]) == 8
    assert len(curation["source_relation_binding"]["rows"]) == 20
    assert "李雨田增补层" in result["snapshot_text"]
    assert "太旺、旺极、太衰、衰极" in result["snapshot_text"]
    assert "未知四态不能由工程三档或人物际遇补造" in result["snapshot_text"]
    assert "dtcw1947_body_vocabulary_semantics_v3 / 3" in result["snapshot_text"]
