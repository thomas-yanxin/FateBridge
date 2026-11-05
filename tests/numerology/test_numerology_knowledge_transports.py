"""New reference retrieval agrees across adapters and binds facts before projection."""

from copy import deepcopy
from dataclasses import replace

import pytest

import fatebridge.application.execution as execution
from fatebridge.services.knowledge import calculate_knowledge_read
from tests.numerology.test_heluo_poem_transports import run_three
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest

rest = shared_rest


@pytest.mark.parametrize("domain", ["heluo", "canping", None])
def test_reference_catalogue_on_actual_local_adapters(domain, rest, tmp_path, capsys):
    payload = {} if domain is None else {"domain": domain}
    response, code, cli, mcp = run_three(
        SPECS["knowledge_registry"],
        payload,
        ["domains", "source", "provenance"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    domains = response.json()["domains"]
    assert len(domains) == (7 if domain is None else 1)
    if domain is None:
        assert [item["domain"] for item in domains[:6]] == [
            "astro",
            "bazi",
            "liureng",
            "qimen",
            "heluo",
            "canping",
        ]
        assert domains[6]["domain"] == "human_design"


@pytest.mark.parametrize(
    "domain,key",
    [
        ("heluo", "乾為天:1"),
        ("heluo", "澤雷隨:1"),
        ("canping", "火.2434.female"),
        ("canping", "火.3034.female"),
        ("canping", "水.3330.unselected"),
        ("canping", "appendix_integer_rounding"),
        ("canping", "bazi_continuous_v1"),
        ("canping", "legacy_minggong_v1"),
    ],
)
def test_actual_reference_facts_and_parts_survive_projection_on_three_adapters(
    domain, key, rest, tmp_path, capsys
):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": domain, "key": key},
        [
            "domain",
            "category",
            "key",
            "citation",
            "reference_only",
            "reference_details",
            "provenance.source_records",
        ],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        SPECS["knowledge_read"].output_model.model_validate(output)
        assert output["reference_only"] is True
        assert output["reference_details"]["personal_applicability_assessed"] is False


@pytest.mark.parametrize(
    "domain,key",
    [
        ("heluo", "乾為天:7"),
        ("heluo", "火.2434.female"),
        ("canping", "乾為天:1"),
        ("canping", "unknown-policy"),
    ],
)
def test_unknown_or_wrong_domain_key_keeps_a_user_error(
    domain, key, rest, tmp_path, capsys
):
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": domain, "key": key},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 400 and code != 0 and mcp.is_error
    assert (
        response.json()["error_code"]
        == cli["error_code"]
        == mcp.structured_content["error_code"]
    )


@pytest.mark.parametrize(
    "fault", ["citation", "conditional_role", "consistent_wrong_card"]
)
@pytest.mark.parametrize("unrelated_projection", [False, True])
def test_actual_request_prevents_forged_reference_even_on_unrelated_projection(
    fault, unrelated_projection, monkeypatch, rest, tmp_path, capsys
):
    payload = dict(domain="canping", key="appendix_integer_rounding")
    output = calculate_knowledge_read(**payload)
    if fault == "citation":
        output["citation"] = "已完成全书独立认证"
    elif fault == "conditional_role":
        output["reference_details"]["record"]["role_by_profile"][
            "bazi_continuous_v1"
        ] = "applied_rule"
    else:
        output = calculate_knowledge_read(domain="canping", key="appendix_month_order")
    original = execution.execute_spec

    def forged(spec, request):
        if spec.key == "knowledge_read":
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(output), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", forged)
    fields = ["source"] if unrelated_projection else ["reference_details"]
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"], payload, fields, rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["retryable"] is False
        assert (
            result["issues"][0]["code"]
            == "runtime_numerology_knowledge_binding_conflict"
        )


def test_reference_conflict_after_metadata_attachment_keeps_source_error(
    monkeypatch, rest, tmp_path, capsys
):
    from fatebridge.services import run_metadata

    original = run_metadata.attach_run_metadata

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get("tool_name") == "knowledge_read":
            result["citation"] = "wrong source after metadata"
        return result

    monkeypatch.setattr(run_metadata, "attach_run_metadata", changed)
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "canping", "key": "legacy_minggong_v1"},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert (
            result["issues"][0]["code"]
            == "runtime_numerology_knowledge_binding_conflict"
        )


@pytest.mark.parametrize("attack", ["catalogue", "source"])
def test_corrupted_actual_reference_source_is_not_hidden_by_projection(
    attack, monkeypatch, rest, tmp_path, capsys
):
    import json

    from fatebridge.core import numerology_knowledge as gateway

    catalogue = json.loads(gateway.CATALOGUE_PATH.read_bytes())
    source = next(e for e in catalogue["sources"] if e["key"] == "schedule_basis")
    data = json.loads((gateway.DATA_ROOT / source["source_path"]).read_bytes())
    data["clauses"][0]["text"] = "Unreviewed replacement"
    target = tmp_path / source["source_path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(gateway.canonical_bytes(data))
    if attack == "catalogue":
        source["canonical_content_sha256"] = "0" * 64
    manifest = tmp_path / "catalogue.json"
    manifest.write_bytes(gateway.canonical_bytes(catalogue))
    monkeypatch.setattr(gateway, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(gateway, "CATALOGUE_PATH", manifest)
    response, code, cli, mcp = run_three(
        SPECS["knowledge_read"],
        {"domain": "canping", "key": "appendix_integer_rounding"},
        ["source"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["retryable"] is False
        assert result["issues"][0]["code"] == "invalid_numerology_knowledge_sources"
