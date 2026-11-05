"""Primary month-duty lists cannot certify hidden-root force coefficients."""

import asyncio
import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.knowledge_store import read_knowledge_entry
from tests.evaluation.test_agentic_nested_outputs import SPECS, business, call_cli
from tests.evaluation.test_agentic_nested_outputs import rest as _rest_fixture
from tests.support.bazi_transport_reader import (
    cli_payload,
    file_payload,
    native_with_manifest,
    save_json,
    verify_identity,
)

rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[2]
CATEGORY = "classical_force_semantics"
KEY = "藏干序位与人元司令"
QUERY = {"domain": "bazi", "category": CATEGORY, "key": KEY}


def test_selected_same_chapter_lists_have_equal_days_and_different_display_order():
    source = json.loads(
        (ROOT / "tests/data/bazi_month_duty_scan_v1/witness-first.json").read_bytes()
    )
    first, second = (p["months"]["巳"]["claims"] for p in source["profiles"])
    assert [(x["canonical_stem"], x["days"]) for x in first] == [
        ("戊", 7),
        ("庚", 5),
        ("丙", 18),
    ]
    assert [(x["canonical_stem"], x["days"]) for x in second] == [
        ("丙", 18),
        ("戊", 7),
        ("庚", 5),
    ]
    assert {x["canonical_stem"]: x["days"] for x in first} == {
        x["canonical_stem"]: x["days"] for x in second
    }
    # Same members and ordinal prose are insufficient to derive these coefficients.
    assert [Fraction(18, 30), Fraction(5, 30), Fraction(7, 30)] != [
        Fraction(4, 7),
        Fraction(2, 7),
        Fraction(1, 7),
    ]
    record = read_knowledge_entry(QUERY)
    curation = record["provenance"]["entry_curation"]
    assert curation["calculation_effect"] == "none"
    assert curation["actual_model_acceptance_for_new_conditions"] == "not_tested"
    assert curation["real_world_predictive_validity"] == "not_tested"
    assert curation["source_refs"][0]["source_pdf_pages"] == list(range(66, 74))
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
    for ref in curation["implementation_refs"]:
        assert (ROOT / ref["source_path"]).is_file()


@pytest.mark.parametrize(
    "tool,payload",
    [("knowledge_read", QUERY), ("knowledge_registry", {"domain": "bazi"})],
)
def test_new_card_and_discovery_cross_actual_transports_at_fixed8192(
    tool, payload, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    flags = {"include_snapshot_text": True, "response_char_limit": 8192}
    result, manifest = asyncio.run(
        native_with_manifest(spec, payload, "2026-10-26T00:00:00Z", flags, tmp_path)
    )
    assert not result.is_error
    values = [file_payload(result.structured_content, manifest, tmp_path, "mcp")]
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "true", "--response-char-limit", "8192"],
    )
    save_json(tmp_path / "cli-original-response.json", cli)
    assert code == 0
    values.append(cli_payload(cli, tmp_path, capsys))
    response = rest.post(spec.rest_path, json=payload, params=flags)
    value = response.json()
    save_json(tmp_path / "rest-original-response.json", value)
    assert response.status_code == 200
    rest_manifest = None
    if value.get("result_delivery"):
        response = rest.get("/api/results/" + value["result_delivery"]["result_id"])
        save_json(tmp_path / "rest-manifest.json", response.json())
        assert response.status_code == 200
        rest_manifest = response.json()
        verify_identity(value["result_delivery"], value["run_metadata"], rest_manifest)
    values.append(file_payload(value, rest_manifest, tmp_path, "rest"))
    assert all(business(v) == business(values[0]) for v in values)
    for value in values:
        spec.output_model.model_validate(value)
    if tool == "knowledge_read":
        assert values[0]["key"] == KEY
    else:
        category = next(
            c
            for d in values[0]["domains"]
            for c in d["categories"]
            if c["name"] == CATEGORY
        )
        assert category["count"] == 14 and KEY in category["keys"]
