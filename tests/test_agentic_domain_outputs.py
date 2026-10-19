"""BaZi dimensions, Sukuyo and reference tools share nested wire contracts."""

import asyncio
import copy
import json
from dataclasses import replace

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaError
from pydantic import ValidationError

import fatebridge.application.execution as execution
import fatebridge.mcp_server as mcp
from fatebridge.cli import run as cli_run
from fatebridge.core.export_contracts import AI_EXPORT_TECHNIQUES
from fatebridge.core.knowledge_store import load_knowledge_bundles, read_knowledge_entry
from fatebridge.core.sukuyo import SU27_ORDER, relation_between_su27
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
    schema_leaf,
)

PROJECTIONS = [
    ("bazi_marriage", "marriage_analysis.spouse_star.spouse_star_positions"),
    ("bazi_career", "career_analysis.industry_analysis.element_distribution.木"),
    ("bazi_wealth", "wealth_analysis.wealth_stars.total_weight"),
    ("bazi_health", "health_analysis.organ_analysis.findings"),
    ("bazi_children", "children_analysis.child_star.positions"),
    ("bazi_education", "education_analysis.wenchang.has_wenchang"),
    ("bazi_personality", "personality_analysis.core_nature.virtue"),
    ("bazi_relatives", "relatives_analysis.parents.father_star_weight"),
    ("bazi_romance", "romance_analysis.opposite_sex_star.weight"),
    ("sukuyo_compatibility", "person1_to_person2.offset"),
    ("knowledge_registry", "provenance.bundle_version"),
    ("knowledge_read", "provenance.coverage.categories"),
    ("export_registry", "selected_technique.settings_template.astroMeaning.enabled"),
    ("export_parse", "settings_used.astroMeaning.qimen.enabled"),
]


@pytest.mark.parametrize("key,field", PROJECTIONS)
@pytest.mark.parametrize("project", [False, True])
def test_full_and_partial_json_match_all_transports(
    key, field, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    request = inputs(spec)
    params = {"as_of": AS_OF, "include_snapshot_text": False}
    flags = {"include_snapshot_text": False}
    cli_flags = ["--no-metadata", "--no-include-snapshot-text"]
    if project:
        params.update(fields=field, strict_fields=True)
        flags.update(fields=[field], strict_fields=True)
        cli_flags += ["--fields", field, "--strict-fields"]
    http = rest.post(spec.rest_path, json=request, params=params)
    protocol = asyncio.run(native(spec, request, **flags))
    code, output = call_cli(spec, request, tmp_path, capsys, cli_flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    assert "run_metadata" not in output and "projection_warnings" not in output
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    for payload in [http.json(), protocol.structured_content, output]:
        spec.output_model.model_validate(payload)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(payload)


BAD_FACTS = [
    (
        "bazi_marriage",
        {
            "marriage_analysis": {
                "spouse_star": {
                    "spouse_star_positions": [{"is_primary": "private-wrong-value"}]
                }
            }
        },
    ),
    (
        "bazi_career",
        {
            "career_analysis": {
                "industry_analysis": {"recommended_industries": [{"industries": [3]}]}
            }
        },
    ),
    (
        "bazi_wealth",
        {
            "wealth_analysis": {
                "wealth_storage": {"storage_hits": [{"opened": "false"}]}
            }
        },
    ),
    (
        "bazi_health",
        {"health_analysis": {"organ_analysis": {"element_distribution": {"木": "1"}}}},
    ),
    (
        "bazi_children",
        {"children_analysis": {"child_star": {"positions": [{"ten_god": 3}]}}},
    ),
    ("bazi_education", {"education_analysis": {"study_stars": {"seal_weight": "1"}}}),
    (
        "bazi_personality",
        {"personality_analysis": {"dominant_traits": {"top_gods": [{"weight": "1"}]}}},
    ),
    (
        "bazi_relatives",
        {"relatives_analysis": {"parents": {"father_star_weight": "1"}}},
    ),
    (
        "bazi_romance",
        {
            "romance_analysis": {
                "timing_context": {"overridden": {"dayun_pillar": "yes"}}
            }
        },
    ),
    ("sukuyo_compatibility", {"person2_to_person1": {"offset": "1"}}),
    ("knowledge_registry", {"domains": [{"categories": [{"count": "1"}]}]}),
    (
        "knowledge_read",
        {"provenance": {"coverage": {"categories": [{"keys_sample": [3]}]}}},
    ),
    (
        "export_registry",
        {"techniques": [{"settings_template": {"planetInfo": {"showHouse": "1"}}}]},
    ),
    (
        "export_parse",
        {"settings_used": {"astroMeaning": {"new-dynamic-key": {"enabled": "1"}}}},
    ),
    ("export_parse", {"sections": [{"included": "false"}]}),
    ("bazi_wealth", {"snapshot_export": {"sections": [{"index": "1"}]}}),
]


@pytest.mark.parametrize("key,payload", BAD_FACTS)
def test_faults_cannot_be_hidden_by_projection(
    key, payload, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS[key]
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(payload)
    with pytest.raises(SchemaError):
        Draft202012Validator(spec.output_model.model_json_schema()).validate(payload)
    original = execution.execute_spec

    def broken_output(actual, request):
        if actual.key == key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(payload), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken_output)
    request = inputs(spec)
    http = rest.post(
        spec.rest_path,
        json=request,
        params={"fields": "snapshot_text", "as_of": AS_OF, "trace_id": "domain-fault"},
    )
    protocol = asyncio.run(
        native(spec, request, fields=["snapshot_text"], trace_id="domain-fault")
    )
    code, output = call_cli(
        spec,
        request,
        tmp_path,
        capsys,
        ["--fields", "snapshot_text", "--trace-id", "domain-fault"],
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert (
        output["error_code"] == "internal_error"
        and output["trace_id"] == "domain-fault"
    )
    assert {
        k: v for k, v in protocol.structured_content.items() if k != "operation"
    } == output
    assert http.json() == {k: v for k, v in output.items() if k != "status_code"}
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    assert "private-wrong-value" not in json.dumps(output)


SCHEMA_LEAVES = [
    (
        "bazi_marriage",
        "marriage_analysis.spouse_star.spouse_star_positions.[].is_primary",
        "boolean",
    ),
    ("bazi_career", "career_analysis.dominant_ten_gods.top_gods.[].weight", "number"),
    ("bazi_wealth", "wealth_analysis.wealth_storage.storage_hits.[].opened", "boolean"),
    ("bazi_health", "health_analysis.organ_analysis.findings.[].organs", "string"),
    ("bazi_children", "children_analysis.affinity.score", "integer"),
    ("bazi_education", "education_analysis.wenchang.hit_pillars.[]", "string"),
    (
        "bazi_personality",
        "personality_analysis.dominant_traits.top_gods.[].weight",
        "number",
    ),
    ("bazi_relatives", "relatives_analysis.parents.father_star_weight", "number"),
    (
        "bazi_romance",
        "romance_analysis.timing_context.overridden.dayun_pillar",
        "boolean",
    ),
    ("bazi_marriage", "marriage_analysis.timing_context.dayun_age", "number"),
    ("sukuyo_compatibility", "person1_to_person2.offset", "integer"),
    ("sukuyo_compatibility", "person1.moon_longitude", "number"),
    (
        "knowledge_registry",
        "domains.[].provenance.coverage.categories.[].count",
        "integer",
    ),
    ("knowledge_read", "query_normalized.object_a", "string"),
    ("knowledge_read", "provenance.coverage.categories.[].keys_sample.[]", "string"),
    (
        "export_registry",
        "techniques.[].settings_template.planetInfo.showHouse",
        "integer",
    ),
    ("export_parse", "settings_used.sections.{}.[]", "string"),
    ("export_parse", "settings_used.astroMeaning.{}.enabled", "integer"),
    ("export_parse", "sections.[].included", "boolean"),
    (
        "bazi_marriage",
        "snapshot_export.technique.settings_template.astroMeaning.enabled",
        "integer",
    ),
]


def test_published_schema_leaves_and_rejections_match(rest, capsys):
    openapi = rest.get("/openapi.json").json()
    manifest = {
        tool["tool"]: tool["output_schema"]
        for tool in rest.get("/api/tools").json()["tools"]
    }

    async def schemas():
        async with Client(mcp.app) as client:
            return {
                tool.name: tool.model_dump(by_alias=True)["outputSchema"]
                for tool in await client.list_tools()
            }

    advertised = asyncio.run(schemas())
    for key, path, expected in SCHEMA_LEAVES:
        spec = SPECS[key]
        central = spec.output_model.model_json_schema()
        assert cli_run(["describe", spec.tool_name]) == 0
        cli = json.loads(capsys.readouterr().out)["output_schema"]
        assert central == cli == manifest[spec.tool_name]
        for root in [central, cli, advertised[spec.tool_name]]:
            Draft202012Validator.check_schema(root)
            assert schema_leaf(root, root, path)["type"] == expected
        http_schema = openapi["paths"][spec.rest_path]["post"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        assert schema_leaf(openapi, http_schema, path)["type"] == expected
    for key, payload in BAD_FACTS:
        with pytest.raises(SchemaError):
            Draft202012Validator(advertised[SPECS[key].tool_name]).validate(payload)


@pytest.mark.parametrize(
    "dimension", [key for key, _ in PROJECTIONS if key.startswith("bazi_")]
)
@pytest.mark.parametrize("gender", ["男", "女", "未知"])
@pytest.mark.parametrize("timing", ["auto", "partial-override", "both-overridden"])
def test_gender_and_timing_variants(dimension, gender, timing):
    spec = SPECS[dimension]
    patch = {"gender": gender}
    request = inputs(spec)
    request.pop("dayun_pillar", None)
    request.pop("liunian_pillar", None)
    if timing == "both-overridden":
        patch.update(dayun_pillar="甲子", liunian_pillar="乙丑")
    elif timing == "partial-override":
        patch.update(dayun_pillar="甲子")
    result = execution.execute_tool(
        spec, spec.request_model.model_validate({**request, **patch})
    )
    if gender == "未知" and timing != "both-overridden":
        # Existing timing derivation rejects an unknown direction. Preserve
        # that domain failure instead of guessing or changing the engine.
        assert result["error_code"] == "validation_error"
        assert result["status_code"] == 400
        return
    assert "error" not in result, result
    spec.output_model.model_validate(result)
    Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
    analysis = result[dimension.removeprefix("bazi_") + "_analysis"]
    assert "timing_context" in analysis
    if timing == "both-overridden":
        assert analysis["timing_context"] == {
            "dayun_pillar": "甲子",
            "liunian_pillar": "乙丑",
            "source": "explicit_pillar_overrides",
            "overridden": {"dayun_pillar": True, "liunian_pillar": True},
        }


@pytest.mark.parametrize("item", AI_EXPORT_TECHNIQUES, ids=lambda item: item["key"])
def test_every_export_technique_has_valid_templates_and_settings(item):
    key = item["key"]
    for tool, request in [
        ("export_registry", {"technique": key}),
        (
            "export_parse",
            {
                "technique": key,
                "content": "[未知章节]\n正文",
                "selected_sections": ["缺失章节"],
                "planet_info": {"showHouse": 1},
                "astro_meaning": {"enabled": 1},
            },
        ),
    ]:
        spec = SPECS[tool]
        result = execution.execute_tool(
            spec, spec.request_model.model_validate(request)
        )
        assert "error" not in result, result
        spec.output_model.model_validate(result)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        if tool == "export_parse":
            assert result["export_text"] == "" and result["missing_selected_sections"]


@pytest.mark.parametrize("domain", ["astro", "bazi", "qimen", "liureng"])
def test_all_knowledge_entries_have_valid_nested_contracts(domain):
    spec = SPECS["knowledge_read"]
    bundle = load_knowledge_bundles()[domain]
    categories = bundle.get("categories", {})
    if domain == "liureng":
        categories = {"shen": bundle["shen_entries"], "house": bundle["jiang_info"]}
    count = 0
    for category, entries in categories.items():
        for key in entries:
            payload = {"domain": domain, "category": category, "key": key}
            if domain == "liureng" and category == "house":
                payload.update(jiang_name=key, tian_branch="子", di_branch="丑")
            result = read_knowledge_entry(payload)
            spec.output_model.model_validate(result)
            Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
            count += 1
    assert count > 0


def test_all_sukuyo_offsets_include_null_distance_compatibility():
    model = SPECS["sukuyo_compatibility"].output_model
    distances = set()
    for self_su in SU27_ORDER:
        for other_su in SU27_ORDER:
            relation = relation_between_su27(self_su, other_su)
            payload = {
                "person1_to_person2": relation,
                "person2_to_person1": relation_between_su27(other_su, self_su),
            }
            model.model_validate(payload)
            Draft202012Validator(model.model_json_schema()).validate(payload)
            distances.add(relation["distance"])
    assert None in distances and len(distances) > 1


@pytest.mark.parametrize("key", [key for key, _ in PROJECTIONS])
def test_extensions_and_original_numeric_types_survive_validation(key):
    spec = SPECS[key]
    payload = business(
        execution.execute_tool(spec, spec.request_model.model_validate(inputs(spec)))
    )

    # Dynamic maps have typed values, so add extensions to model objects, not
    # to arbitrary dictionary namespaces (a new key there needs a valid value).
    def extend_objects(value, schema, root):
        if "$ref" in schema:
            schema = root["$defs"][schema["$ref"].split("/")[-1]]
        if "anyOf" in schema:
            schema = next(
                item for item in schema["anyOf"] if item.get("type") != "null"
            )
            return extend_objects(value, schema, root)
        if isinstance(value, dict):
            properties = schema.get("properties", {})
            if properties:
                for name, child in list(value.items()):
                    if name in properties:
                        extend_objects(child, properties[name], root)
                value["future_fact"] = {"value": [None, 1, "原样保留"]}
            elif isinstance(schema.get("additionalProperties"), dict):
                for child in value.values():
                    extend_objects(child, schema["additionalProperties"], root)
        elif isinstance(value, list):
            for child in value:
                extend_objects(child, schema.get("items", {}), root)

    schema = spec.output_model.model_json_schema()
    extend_objects(payload, schema, schema)
    before = copy.deepcopy(payload)
    spec.output_model.model_validate(payload)
    Draft202012Validator(schema).validate(payload)
    assert payload == before
    fake = replace(spec, bind=lambda _: (lambda: payload, (), {}))
    assert (
        execution.execute_spec(fake, spec.request_model.model_validate(inputs(spec)))
        is payload
    )


@pytest.mark.parametrize(
    "key,payload",
    [
        (
            "sukuyo_compatibility",
            {
                "person1_date": "1990-06-15",
                "person1_time": "08:30:00",
                "person2_date": "1990-06-15",
                "person2_time": "08:30:00",
            },
        ),
        ("knowledge_registry", {}),
        ("knowledge_read", {"domain": "bazi", "category": "ten_gods", "key": "比肩"}),
        ("knowledge_read", {"domain": "qimen", "category": "door", "key": "休"}),
        (
            "knowledge_read",
            {
                "domain": "liureng",
                "category": "house",
                "jiang_name": "天乙",
                "tian_branch": "子",
                "di_branch": "丑",
            },
        ),
        ("export_registry", {}),
        ("export_parse", {"technique": "generic", "content": ""}),
    ],
)
def test_nondefault_reference_results_match_transports(
    key, payload, rest, tmp_path, capsys
):
    spec = SPECS[key]
    http = rest.post(spec.rest_path, json=payload, params={"as_of": AS_OF})
    protocol = asyncio.run(native(spec, payload))
    code, output = call_cli(spec, payload, tmp_path, capsys, ["--no-metadata"])
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    spec.output_model.model_validate(output)
    Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
    if key == "sukuyo_compatibility":
        assert output["person1_to_person2"]["offset"] == 0
        assert output["person1_to_person2"]["distance"] is None


@pytest.mark.parametrize("partial", [False, True])
def test_auto_timing_fractional_years_match_all_transports(
    partial, rest, tmp_path, capsys
):
    spec = SPECS["bazi_marriage"]
    payload = inputs(spec)
    payload.pop("dayun_pillar", None)
    payload.pop("liunian_pillar", None)
    if partial:
        payload["dayun_pillar"] = "甲子"
    field = "marriage_analysis.timing_context.dayun_age"
    http = rest.post(
        spec.rest_path,
        json=payload,
        params={"as_of": AS_OF, "fields": field, "strict_fields": True},
    )
    protocol = asyncio.run(native(spec, payload, fields=[field], strict_fields=True))
    code, output = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        ["--no-metadata", "--fields", field, "--strict-fields"],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    assert isinstance(output["marriage_analysis"]["timing_context"]["dayun_age"], float)


@pytest.mark.parametrize(
    "dimension", [key for key, _ in PROJECTIONS if key.startswith("bazi_")]
)
def test_unknown_timing_direction_preserves_existing_domain_failure(
    dimension, rest, tmp_path, capsys
):
    spec = SPECS[dimension]
    payload = inputs(spec)
    payload.pop("dayun_pillar", None)
    payload.pop("liunian_pillar", None)
    payload["gender"] = "未知"
    http = rest.post(
        spec.rest_path,
        json=payload,
        params={"as_of": AS_OF, "trace_id": "unknown-direction"},
    )
    protocol = asyncio.run(native(spec, payload, trace_id="unknown-direction"))
    code, output = call_cli(
        spec, payload, tmp_path, capsys, ["--trace-id", "unknown-direction"]
    )
    assert http.status_code == 400 and protocol.is_error and code == 1
    assert output["error_code"] == "validation_error" and output["retryable"] is False
    assert http.json() == {k: v for k, v in output.items() if k != "status_code"}
    assert {
        k: v for k, v in protocol.structured_content.items() if k != "operation"
    } == output
