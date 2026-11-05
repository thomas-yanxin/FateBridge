"""A source correction reaches public knowledge without rewriting old editions."""

import asyncio
from pathlib import Path

from fatebridge.services.knowledge import calculate_knowledge_read
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[1]
TARGET = ("classical_force_semantics", "物理藏根与功能根")


def test_same_source_root_contrast_is_queryable_and_snapshot_keeps_final_judgment():
    result = calculate_knowledge_read(domain="bazi", category=TARGET[0], key=TARGET[1])
    assert "error" not in result
    assert "最终以癸水仍得通根判戊癸合而不化" in result["rendered_text"]
    assert "后造才明言合而必化" in result["snapshot_text"]
    curation = result["provenance"]["entry_curation"]
    assert curation["entry_revision"] == 2
    source = curation["source_refs"][-1]
    assert source["source_pdf_pages"] == [209, 210]
    assert source["source_sha256"] == (
        "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert source["edition"] in result["snapshot_text"]
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    indices = sum(
        (
            curation[k]
            for k in (
                "classical_condition_tip_indexes",
                "implementation_tip_indexes",
                "editorial_tip_indexes",
            )
        ),
        [],
    )
    assert sorted(indices) == list(range(7))


def test_current_root_card_is_identical_on_rest_native_mcp_and_cli(
    rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "category": TARGET[0], "key": TARGET[1]}
    opts = {"include_snapshot_text": False, "response_char_limit": 0}
    http = rest.post(spec.rest_path, json=payload, params=opts)
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "false", "--response-char-limit", "0"],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    assert http.json()["provenance"]["entry_curation"]["entry_revision"] == 2
