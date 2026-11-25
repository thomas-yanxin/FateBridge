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
from fatebridge.core.sukuyo.sukuyo import SU27_ORDER, relation_between_su27
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    capability_contracts,
    inputs,
)
from tests.unit_test.fixtures.schema_assertions import schema_leaf

PROJECTIONS = [
    ("bazi_marriage", "marriage_analysis.evidence_chain.topic.palaces.day"),
    ("bazi_career", "career_analysis.evidence_chain.topic.first_view.natal_stars"),
    ("bazi_wealth", "wealth_analysis.evidence_chain.topic.storage_matches"),
    ("bazi_health", "health_analysis.evidence_chain.topic.scope"),
    ("bazi_children", "children_analysis.evidence_chain.topic.palaces.hour"),
    ("bazi_education", "education_analysis.evidence_chain.topic.markers"),
    ("bazi_personality", "personality_analysis.evidence_chain.topic.first_view"),
    ("bazi_relatives", "relatives_analysis.evidence_chain.topic.palaces.year"),
    ("bazi_romance", "romance_analysis.evidence_chain.topic.selection_alternatives"),
    ("sukuyo_compatibility", "person1_to_person2.offset"),
    ("knowledge_registry", "provenance.coverage.categories"),
    ("knowledge_read", "provenance.coverage.categories"),
    ("export_registry", "selected_technique.settings_template.astroMeaning.enabled"),
    ("export_parse", "settings_used.astroMeaning.qimen.enabled"),
]


@pytest.mark.parametrize("key,field", PROJECTIONS)
@pytest.mark.parametrize("project", [False, True])
def test_full_and_partial_json_match_all_transports(
    key, field, project: bool, surface_calls
) -> None:
    spec = SPECS[key]
    request = inputs(spec)
    params = {"as_of": AS_OF, "include_snapshot_text": False}
    flags = {"include_snapshot_text": False}
    cli_flags = ["--no-metadata", "--no-include-snapshot-text"]
    if project:
        params.update(fields=field, strict_fields=True)
        flags.update(fields=[field], strict_fields=True)
        cli_flags += ["--fields", field, "--strict-fields"]
    else:
        pass
    http, protocol, code, output = surface_calls(
        spec, request, params=params, options=flags, flags=cli_flags, cli_first=False
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    assert "run_metadata" not in output and "projection_warnings" not in output
    for payload in [http.json(), protocol.structured_content, output]:
        spec.output_model.model_validate(payload)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(payload)


TOPIC_LEAVES = [
    ("marriage", "palaces.{}.pillar", "string", {"palaces": {"day": {"pillar": 4}}}),
    (
        "career",
        "first_view.natal_stars.[].visible_in.[]",
        "string",
        {"first_view": {"natal_stars": [{"visible_in": [3]}]}},
    ),
    (
        "wealth",
        "storage_matches.[].branch",
        "string",
        {"storage_matches": [{"branch": "private-wrong-value", "element": 1}]},
    ),
    ("health", "scope", "string", {"scope": 3}),
    ("children", "palaces.{}.pillar", "string", {"palaces": {"hour": {"pillar": 3}}}),
    (
        "education",
        "markers.[].natal_positions.[]",
        "string",
        {"markers": [{"natal_positions": [3]}]},
    ),
    (
        "personality",
        "first_view.timing.[].palace_relation_count",
        "integer",
        {"first_view": {"timing": [{"palace_relation_count": "1"}]}},
    ),
    (
        "relatives",
        "palaces.{}.relations",
        "array",
        {"palaces": {"year": {"relations": "invalid"}}},
    ),
]

BAD_FACTS = [
    (f"bazi_{topic}", {f"{topic}_analysis": {"evidence_chain": {"topic": invalid}}})
    for topic, _, _, invalid in TOPIC_LEAVES
] + [
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
    key, payload, monkeypatch: pytest.MonkeyPatch, surface_calls
) -> None:
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
        else:
            pass
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken_output)
    request = inputs(spec)
    http, protocol, code, output = surface_calls(
        spec,
        request,
        params={"fields": "snapshot_text", "as_of": AS_OF, "trace_id": "domain-fault"},
        options={"fields": ["snapshot_text"], "trace_id": "domain-fault"},
        flags=["--fields", "snapshot_text", "--trace-id", "domain-fault"],
        cli_first=False,
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
    assert "private-wrong-value" not in json.dumps(output)


SCHEMA_LEAVES = [
    (f"bazi_{topic}", f"{topic}_analysis.evidence_chain.topic.{path}", kind)
    for topic, path, kind, _ in TOPIC_LEAVES
] + [
    (
        "bazi_romance",
        "romance_analysis.timing_context.overridden.dayun_pillar",
        "boolean",
    ),
    ("bazi_marriage", "marriage_analysis.timing_context.dayun_age", "number"),
    ("sukuyo_compatibility", "person1_to_person2.offset", "integer"),
    ("sukuyo_compatibility", "person1.calendar.lunar_day", "integer"),
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


def test_published_schema_leaves_and_rejections_match(
    rest, capsys: pytest.CaptureFixture[str]
) -> None:
    openapi = rest.get("/openapi.json").json()
    manifest = {
        tool["tool"]: tool["output_schema"]
        for tool in rest.get("/api/tools").json()["tools"]
    }

    async def schemas():
        async with Client(mcp.app) as client:
            return {
                name: contract["output_schema"]
                for name, contract in (
                    await capability_contracts(client, detail="full")
                ).items()
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
def test_gender_and_timing_variants(dimension, gender: str, timing: str) -> None:
    spec = SPECS[dimension]
    patch = {"gender": gender}
    request = inputs(spec)
    request.pop("dayun_pillar", None)
    request.pop("liunian_pillar", None)
    if timing == "both-overridden":
        patch.update(dayun_pillar="甲子", liunian_pillar="乙丑")
    elif timing == "partial-override":
        patch.update(dayun_pillar="甲子")
    else:
        pass
    result = execution.execute_tool(
        spec, spec.request_model.model_validate({**request, **patch})
    )
    assert "error" not in result, result
    spec.output_model.model_validate(result)
    Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
    analysis = result[dimension.removeprefix("bazi_") + "_analysis"]
    assert "timing_context" in analysis
    if gender == "未知" and timing != "both-overridden":
        assert analysis["timing_context"]["dayun_status"] == (
            "explicit_override"
            if timing == "partial-override"
            else "unavailable_gender_direction"
        )
        assert analysis["timing_context"]["liunian_pillar"]
    else:
        pass
    if timing == "both-overridden":
        assert analysis["timing_context"] == {
            "dayun_pillar": "甲子",
            "liunian_pillar": "乙丑",
            "source": "explicit_pillar_overrides",
            "overridden": {"dayun_pillar": True, "liunian_pillar": True},
        }
    else:
        pass


@pytest.mark.parametrize("item", AI_EXPORT_TECHNIQUES, ids=lambda item: item["key"])
def test_every_export_technique_has_valid_templates_and_settings(item) -> None:
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
        else:
            pass


@pytest.mark.parametrize("domain", ["astro", "bazi", "qimen", "liureng"])
def test_all_knowledge_entries_have_valid_nested_contracts(domain: str) -> None:
    spec = SPECS["knowledge_read"]
    bundle = load_knowledge_bundles()[domain]
    categories = bundle.get("categories", {})
    if domain == "liureng":
        categories = {"shen": bundle["shen_entries"], "house": bundle["jiang_info"]}
    else:
        pass
    count = 0
    for category, entries in categories.items():
        for key in entries:
            payload = {"domain": domain, "category": category, "key": key}
            if domain == "liureng" and category == "house":
                payload.update(jiang_name=key, tian_branch="子", di_branch="丑")
            else:
                pass
            result = read_knowledge_entry(payload)
            spec.output_model.model_validate(result)
            Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
            count += 1
    assert count > 0


def test_all_sukuyo_offsets_preserve_primary_text_groups_without_invented_distances() -> (
    None
):
    model = SPECS["sukuyo_compatibility"].output_model
    distances = set()
    groups = set()
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
            groups.add(relation["sequence_group"])
    assert distances == {None}
    assert groups == {1, 2, 3}


@pytest.mark.parametrize("key", ["knowledge_registry", "knowledge_read"])
def test_reference_responses_do_not_expose_cached_coverage(key: str) -> None:
    spec = SPECS[key]
    request = spec.request_model.model_validate(inputs(spec))
    first = business(execution.execute_tool(spec, request))
    expected = copy.deepcopy(first)
    provenance = (
        first["domains"][0]["provenance"]
        if key == "knowledge_registry"
        else first["provenance"]
    )
    coverage = provenance["coverage"]
    coverage["future_fact"] = {"value": "caller-owned annotation"}
    coverage["categories"][0]["keys_sample"].append("caller-owned key")
    assert business(execution.execute_tool(spec, request)) == expected


@pytest.mark.parametrize("key", [key for key, _ in PROJECTIONS])
def test_extensions_and_original_numeric_types_survive_validation(key) -> None:
    spec = SPECS[key]
    request = spec.request_model.model_validate(inputs(spec))
    payload = execution.execute_spec(spec, request)

    # Dynamic maps have typed values, so add extensions to model objects, not
    # to arbitrary dictionary namespaces (a new key there needs a valid value).
    closed_objects = []

    def extend_objects(value, schema, root):
        if "$ref" in schema:
            schema = root["$defs"][schema["$ref"].split("/")[-1]]
        else:
            pass
        if "anyOf" in schema:
            schema = next(
                item for item in schema["anyOf"] if item.get("type") != "null"
            )
            return extend_objects(value, schema, root)
        else:
            pass
        if isinstance(value, dict):
            properties = schema.get("properties", {})
            if properties:
                for name, child in list(value.items()):
                    if name in properties:
                        extend_objects(child, properties[name], root)
                    else:
                        pass
                if schema.get("additionalProperties") is False:
                    closed_objects.append(value)
                else:
                    value["future_fact"] = {"value": [None, 1, "原样保留"]}
            elif isinstance(schema.get("additionalProperties"), dict):
                for child in value.values():
                    extend_objects(child, schema["additionalProperties"], root)
            else:
                pass
        elif isinstance(value, list):
            for child in value:
                extend_objects(child, schema.get("items", {}), root)
        else:
            pass

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
    if closed_objects:
        # Closed fact records stay closed. Extension preservation must never
        # be implemented by relaxing their published additionalProperties.
        closed = closed_objects[0]
        closed["future_fact"] = {"value": [None, 1, "必须拒绝"]}
        try:
            with pytest.raises(ValidationError):
                spec.output_model.model_validate(payload)
            with pytest.raises(SchemaError):
                Draft202012Validator(schema).validate(payload)
        finally:
            del closed["future_fact"]
    else:
        pass


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
        ("knowledge_read", {"domain": "astro", "category": "planet", "key": "Mars"}),
        (
            "knowledge_read",
            {"domain": "astro", "category": "aspect", "aspect_degree": 90},
        ),
        ("knowledge_read", {"domain": "qimen", "category": "door", "key": "休"}),
        ("knowledge_read", {"domain": "qimen", "category": "stem", "key": "戊"}),
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
    key: str, payload, surface_calls
) -> None:
    spec = SPECS[key]
    http, protocol, code, output = surface_calls(
        spec, payload, params={"as_of": AS_OF}, flags=["--no-metadata"], cli_first=False
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    spec.output_model.model_validate(output)
    Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
    if key == "knowledge_read" and payload["domain"] in {"astro", "qimen"}:
        assert output["provenance"]["reference_only"] is True
        assert output["lines"] and output["citation"]
        if payload["domain"] == "qimen" and payload["category"] == "stem":
            assert output["lines"] == ["六仪之一，藏甲子。"]
            assert "《遁甲演义》卷三·奇遁布局法" in output["citation"]
        else:
            pass
    else:
        pass
    if key == "sukuyo_compatibility":
        assert output["person1_to_person2"]["offset"] == 0
        assert output["person1_to_person2"]["distance"] is None
    else:
        pass


@pytest.mark.parametrize("partial", [False, True])
def test_auto_timing_fractional_years_match_all_transports(
    partial: bool, surface_calls
) -> None:
    spec = SPECS["bazi_marriage"]
    payload = inputs(spec)
    payload.pop("dayun_pillar", None)
    payload.pop("liunian_pillar", None)
    if partial:
        payload["dayun_pillar"] = "甲子"
    else:
        pass
    field = "marriage_analysis.timing_context.dayun_age"
    http, protocol, code, output = surface_calls(
        spec,
        payload,
        params={"as_of": AS_OF, "fields": field, "strict_fields": True},
        options={"fields": [field], "strict_fields": True},
        flags=["--no-metadata", "--fields", field, "--strict-fields"],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    assert isinstance(output["marriage_analysis"]["timing_context"]["dayun_age"], float)


@pytest.mark.parametrize(
    "dimension", [key for key, _ in PROJECTIONS if key.startswith("bazi_")]
)
def test_unknown_timing_direction_preserves_available_layers_across_transports(
    dimension, surface_calls
) -> None:
    spec = SPECS[dimension]
    payload = inputs(spec)
    payload.pop("dayun_pillar", None)
    payload.pop("liunian_pillar", None)
    payload["gender"] = "未知"
    http, protocol, code, output = surface_calls(
        spec,
        payload,
        params={"as_of": AS_OF, "trace_id": "unknown-direction"},
        options={"trace_id": "unknown-direction"},
        flags=["--trace-id", "unknown-direction", "--no-metadata"],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    analysis = output[dimension.removeprefix("bazi_") + "_analysis"]
    assert analysis["timing_context"]["dayun_status"] == "unavailable_gender_direction"
    assert analysis["timing_context"]["dayun_pillar"] is None
    assert analysis["timing_context"]["liunian_pillar"]
