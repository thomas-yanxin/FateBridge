"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.application.result_delivery as delivery
import fatebridge.services.jyotish as service
from fatebridge.application.description import describe_spec
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.jyotish_pinda import METHOD, PLANETS, SOURCE
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services import astrology, jyotish
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.surface_payloads import astro_payload
from tests.jyotish.test_jyotish_civil_instant import BIRTH
from tests.jyotish.test_jyotish_clock_sources import arguments
from tests.jyotish.test_jyotish_fidelity import CUSP
from tests.jyotish.test_jyotish_sources import data18, restore_runtime
from tests.jyotish.test_jyotish_transports import AS_OF, SPECS, call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
@pytest.mark.parametrize("solar", [False, True])
def test_recorded_instant_and_solar_label_survive_three_surfaces(
    monkeypatch, capsys, key, solar
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {**BIRTH, "divisions": [], "use_true_solar_time": solar},
        ["person_info.utc_datetime", "india.profile.clock_context", "india.charts.D1"],
    )
    assert result["person_info"]["utc_datetime"] == "1990-04-06T01:33:00+00:00"
    context = result["india"]["profile"]["clock_context"]
    assert context["calculation_utc_datetime"] == "1990-04-06T01:33:00+00:00"
    assert context["physical_instant_shifted"] is False
    assert context["solar_display_requested"] is solar
    if solar:
        assert context["solar_wall_datetime"].startswith("1990-04-06T09:36:")
        assert "+" not in context["solar_wall_datetime"]
    else:
        assert context["solar_wall_datetime"] is None


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_nested_clock_projection_preserves_model_window_independence(
    monkeypatch, capsys, key
):
    payload = {
        **BIRTH,
        "birth_year": 2051,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 0,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "birth_longitude": -180,
        "birth_latitude": 0,
        "divisions": [],
        "use_true_solar_time": True,
        "cheshta_model": "simon1994_j2000",
    }
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2052
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.profile.clock_context.solar_wall_datetime",
            "india.profile.clock_context.calculation_utc_datetime",
            "india.profile.clock_context.physical_instant_shifted",
            "india.strengths.cheshta_bala.model_context.status",
        ],
    )
    context = result["india"]["profile"]["clock_context"]
    assert context["solar_wall_datetime"].startswith("2050-12-31T")
    assert context["calculation_utc_datetime"] == "2051-01-01T00:00:00+00:00"
    assert context["physical_instant_shifted"] is False
    assert (
        result["india"]["strengths"]["cheshta_bala"]["model_context"]["status"]
        == "outside_validated_model_window"
    )


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
def test_clock_to_native_change_is_typed_and_uniform_sources_succeed_on_all_surfaces(
    data18, tmp_path, monkeypatch, capsys, key
):
    _, full = data18
    empty = tmp_path / "empty"
    empty.mkdir()
    module, name = (
        (jyotish, "build_astro_birth_info")
        if key == "astro_vimshottari"
        else (astrology, "_build_birth_info")
    )
    original = getattr(module, name)
    mutate = True

    def changed(*args, **kwargs):
        birth = original(*args, **kwargs)
        if mutate:
            monkeypatch.setenv("SE_EPHE_PATH", str(full))
            e.configure_ephemeris_path(str(full))
        return birth

    monkeypatch.setattr(module, name, changed)
    payload = {"name": "虚构：太阳钟时来源衔接", **arguments()}
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    spec = next(s for s in CATALOG if s.key == key)
    fields = ["india.profile.clock_context", "india.birth_time_sensitivity"]
    options = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
        "as_of": "2026-10-22T00:00:00Z",
    }
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )

    def select(directory):
        monkeypatch.setenv("SE_EPHE_PATH", str(directory))
        e.configure_ephemeris_path(str(directory))

    def surfaces(directory):
        params = [("fields", f) for f in fields] + [
            (k, str(v).lower() if isinstance(v, bool) else str(v))
            for k, v in options.items()
            if k != "fields"
        ]
        select(directory)
        rest = TestClient(api.app).post(spec.rest_path, json=payload, params=params)

        async def protocol():
            async with Client(create_mcp_app()) as client:
                return await client.call_tool(
                    spec.tool_name, {**payload, **options}, raise_on_error=False
                )

        select(directory)
        mcp = asyncio.run(protocol())
        capsys.readouterr()
        select(directory)
        code = run(
            [
                spec.tool_name,
                "--subject-file",
                str(request),
                "--fields",
                *fields,
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
                "--as-of",
                options["as_of"],
            ]
        )
        return rest, mcp, code, json.loads(capsys.readouterr().out)

    rest, mcp, code, cli = surfaces(empty)
    assert rest.status_code == 503 and mcp.is_error and code == 1
    for result in [rest.json(), json.loads(mcp.content[0].text), cli]:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "physical_configuration_changed"}
        ]
        assert str(tmp_path) not in json.dumps(result)

    mutate = False
    for directory, model in [(empty, "moshier"), (full, "swieph")]:
        rest, mcp, code, cli = surfaces(directory)
        assert rest.status_code == 200 and not mcp.is_error and code == 0
        results = [rest.json(), mcp.structured_content, cli]
        assert results[0]["india"] == results[1]["india"] == results[2]["india"]
        for result in results:
            clock = result["india"]["profile"]["clock_context"]
            assert clock["input_clock_conversion"][
                "solar_ephemeris_models_observed"
            ] == [model]
            checked = clock["source_comparison"]
            assert checked["status"] == "compatible_observed_sun_contexts"
            assert checked["physical_instant_shifted"] is False
            assert checked["original_sun_identity_recorded"] is True
            grid = result["india"]["birth_time_sensitivity"]
            assert (
                len(grid["source_comparison"]["sample_source_indices"])
                == grid["sample_count"]
            )


@pytest.mark.parametrize(
    "basis", ["sidereal_365_25636", "tropical_365_2425", "savana_360"]
)
@pytest.mark.parametrize("projected", [False, True])
def test_common_epoch_and_string_fractions_on_all_real_surfaces(
    monkeypatch, capsys, basis, projected
):
    depth = 2 if projected else 6
    fields = (
        [
            "vimshottari.time_quantization.source_mansion_fraction_exact",
            "vimshottari.birth_balance.elapsed_microseconds",
        ]
        if projected
        else [
            "vimshottari.time_quantization",
            "vimshottari.birth_balance",
            "vimshottari.subdivisions",
            "vimshottari.birth_time_sensitivity",
            "india.rulesets",
            "india.rule_trace",
        ]
    )
    body = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        {
            **astro_payload(),
            "analysis_year": 2026,
            "divisions": [],
            "birth_time_uncertainty_minutes": 1,
            "dasha_depth": depth,
            "year_basis": basis,
        },
        fields,
    )
    vim = body["vimshottari"]
    fraction = vim["time_quantization"]["source_mansion_fraction_exact"]
    assert all(type(fraction[k]) is str for k in ["numerator", "denominator"])
    assert type(vim["birth_balance"]["elapsed_microseconds"]) is int
    if projected:
        assert set(vim["time_quantization"]) == {"source_mansion_fraction_exact"}
    else:
        assert (
            vim["subdivisions"]["epoch_context"]["reference_epoch_utc"]
            == vim["time_quantization"]["reference_epoch_utc"]
        )
        assert all(
            type(v) is str
            for v in vim["subdivisions"]["epoch_context"][
                "complete_major_start_offset_microseconds_fraction"
            ].values()
        )
        assert len(vim["subdivisions"]["current_levels"]) == 6
        assert all(
            "time_quantization" in s for s in vim["birth_time_sensitivity"]["samples"]
        )
        sources = {row["id"]: row for row in body["india"]["rulesets"]}
        assert (
            sources[vim["time_quantization"]["source_id"]]["source_kind"]
            == "implementation_policy"
        )
    definitions = SPECS["astro_vimshottari"].output_model.model_json_schema()["$defs"]
    assert (
        "DashaExactFraction" in definitions and "DashaTimeQuantization" in definitions
    )


def test_same_run_exact_fraction_claims_reject_numeric_coercion():
    spec = SPECS["astro_vimshottari"]
    body = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                **astro_payload(),
                "analysis_year": 2026,
                "divisions": [],
                "dasha_depth": 6,
            }
        ),
        options=ExecutionOptions(as_of=AS_OF),
    )
    meta = body["run_metadata"]
    fraction = body["vimshottari"]["time_quantization"]["source_mansion_fraction_exact"]
    claims = [
        CalculationClaim(
            path=f"vimshottari.time_quantization.source_mansion_fraction_exact.{key}",
            value=fraction[key],
            run_id=meta["run_id"],
            business_output_sha256=meta["business_output_sha256"],
        )
        for key in ["numerator", "denominator"]
    ]
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    changed = copy.deepcopy(claims)
    changed[0].value = int(fraction["numerator"])
    rejected = verify_calculation_claims(body, changed)
    assert rejected["status"] == "rejected"
    assert any(
        error["code"] == "value_or_type_mismatch" for error in rejected["errors"]
    )


@pytest.mark.parametrize("depth", [3, 6])
@pytest.mark.parametrize("projected", [False, True])
def test_nested_periods_on_real_rest_mcp_cli(monkeypatch, capsys, depth, projected):
    fields = (
        ["vimshottari.subdivisions.current_levels", "vimshottari.subdivisions.depth"]
        if projected
        else [
            "summary",
            "vimshottari.subdivisions",
            "vimshottari.birth_time_sensitivity",
            "vimshottari.natal_ruler_context",
        ]
    )
    body = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        {
            **astro_payload(),
            "analysis_year": 2026,
            "divisions": [],
            "birth_time_uncertainty_minutes": 1,
            "dasha_depth": depth,
        },
        fields,
    )
    v = body["vimshottari"]
    s = v["subdivisions"]
    assert len(s["current_levels"]) == s["depth"] == depth
    if projected:
        assert set(s) == {"current_levels", "depth"}
    else:
        assert all(
            len(g["period_lord_chain"]) == depth
            for g in v["birth_time_sensitivity"]["stage_variants"]
        )
        assert all(len(g["periods"]) == 9 for g in s["siblings_by_level"])
        assert all(p["period_roles"] for p in v["natal_ruler_context"])
    defs = SPECS["astro_vimshottari"].output_model.model_json_schema()["$defs"]
    assert all(
        key in defs for key in ["DashaSubdivisions", "DashaLevel", "DashaSiblings"]
    )
    assert "dasha_levels" in describe_spec(SPECS["astro_vimshottari"])["evidence_views"]


def test_saved_full_nested_result_pages_and_claims_do_not_recompute(
    monkeypatch, tmp_path
):
    store = delivery.ResultStore(tmp_path / "nested-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)
    response = client.post(
        "/api/astro/vimshottari",
        json={
            **astro_payload(),
            "analysis_year": 2026,
            "dasha_depth": 6,
            "divisions": [],
            "birth_time_uncertainty_minutes": 1,
        },
        params={
            "as_of": AS_OF,
            "include_snapshot_text": "true",
            "response_char_limit": 4096,
        },
    )
    assert response.status_code == 200, response.text
    shaped = response.json()
    ref = shaped["result_delivery"]

    def forbidden(*args, **kwargs):
        pytest.fail("Same-run nested pages cannot recalculate periods")

    monkeypatch.setattr(service, "calculate_vimshottari", forbidden)
    chunks = []
    offset = 0
    while True:
        page = client.get(
            f"/api/results/{ref['result_id']}/pages", params={"offset": offset}
        )
        assert page.status_code == 200
        item = page.json()
        chunks.append(item["text"])
        if item["next_offset"] is None:
            break
        offset = item["next_offset"]
    text = "".join(chunks)
    assert hashlib.sha256(text.encode()).hexdigest() == ref["sha256"]
    full = json.loads(text)
    meta = full["run_metadata"]
    assert meta["run_id"] == shaped["run_metadata"]["run_id"]
    assert len(full["vimshottari"]["subdivisions"]["current_levels"]) == 6
    claims = [
        CalculationClaim(
            path=f"vimshottari.subdivisions.current_levels.{i}.{field}",
            value=row[field],
            run_id=meta["run_id"],
            business_output_sha256=meta["business_output_sha256"],
        )
        for i, row in enumerate(full["vimshottari"]["subdivisions"]["current_levels"])
        for field in ["lord", "start", "end"]
    ]
    assert (
        verify_calculation_claims(full, claims)["status"] == "verified_structured_facts"
    )
    incomplete = copy.deepcopy(full)
    assert "snapshot_text" in incomplete
    del incomplete["snapshot_text"]
    rejected = verify_calculation_claims(incomplete, claims)
    assert rejected["status"] == "rejected"
    assert {"code": "incomplete_or_changed_business_payload"} in rejected["errors"]
    bad = copy.deepcopy(claims)
    bad[-1].value = "2000-01-01T00:00:00+00:00"
    assert verify_calculation_claims(full, bad)["status"] == "rejected"


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("sapta", ["santhanam_27", "raman_30"])
def test_independently_selected_drekkana_and_conflict_survive_real_surfaces(
    monkeypatch, capsys, key, sapta
):
    payload = {
        **astro_payload(),
        "saptavargaja_profile": sapta,
        "drekkana_profile": "raman_36",
        "divisions": [],
        "birth_time_uncertainty_minutes": 0,
    }
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.profile.drekkana_profile",
            "india.strengths.sthana_bala",
            "india.birth_time_sensitivity.sthana_bala_sample_ranges",
            "india.topic_evidence",
            "india.rule_trace",
        ],
    )
    india = result["india"]
    strength = india["strengths"]["sthana_bala"]
    assert (
        india["profile"]["drekkana_profile"]
        == strength["profile"]["drekkana_profile"]["id"]
        == "raman_36"
    )
    assert strength["profile"]["id"] == sapta
    assert strength["source_reading_conflicts"][0]["summary_value_virupa"] == 60
    for planet, values in strength["summary"].items():
        assert (
            strength["drekkana_profile_comparison"]["raman_36"][planet]["total_virupa"]
            == values["total_virupa"]
        )
        assert india["birth_time_sensitivity"]["sthana_bala_sample_ranges"][planet][
            "total_virupa"
        ] == {"minimum": values["total_virupa"], "maximum": values["total_virupa"]}


def test_conflicting_primary_coefficient_supports_nested_strict_projection(
    monkeypatch, capsys
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        {**astro_payload(), "drekkana_profile": "raman_36"},
        [
            "india.strengths.sthana_bala.profile.drekkana_profile.source_section",
            "india.strengths.sthana_bala.source_reading_conflicts",
            "india.strengths.sthana_bala.drekkana_profile_comparison.raman_36.Venus.total_virupa",
        ],
    )
    assert (
        result["india"]["strengths"]["sthana_bala"]["source_reading_conflicts"][0][
            "detailed_value_virupa"
        ]
        == 15
    )


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_uncertainty_and_star_candidates_survive_three_surfaces(
    monkeypatch, capsys, key
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {**CUSP, "divisions": [], "birth_time_uncertainty_minutes": 2},
        [
            "summary",
            "india.reading_basis",
            "india.birth_time_sensitivity",
            "india.topic_evidence",
        ],
    )
    assert "名义生时" in result["summary"]
    basis = result["india"]["reading_basis"]
    assert basis["reference"] == "nominal_birth_instant"
    assert basis["options_basis"] == "sampled_grid"
    assert {x["name"] for x in basis["moon_nakshatra_options"]} == {
        "Magha",
        "Purva Phalguni",
    }
    sensitivity = result["india"]["birth_time_sensitivity"]
    assert len(sensitivity["nakshatra_sampled_points"]) == 10
    assert (
        sum(x["sample_count"] for x in sensitivity["nakshatra_alternatives"]["Moon"])
        == sensitivity["sample_count"]
    )
    for topic in result["india"]["topic_evidence"].values():
        for factor in topic["factors"]:
            context = factor.get("calculation_context")
            if not context:
                continue
            assert context["computed_scenario_count"] <= context["scenario_count"]
            if context["value_status"] == "conditional_results":
                assert factor["fact"] is None
                assert "不能当作零或缺项" in factor["traditional_interpretation"]


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_nested_reading_basis_projection_keeps_both_padas(monkeypatch, capsys, key):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {**CUSP, "birth_time_uncertainty_minutes": 2},
        [
            "india.reading_basis.moon_nakshatra_options",
        ],
    )
    assert {
        x["pada"] for x in result["india"]["reading_basis"]["moon_nakshatra_options"]
    } == {1, 4}


def test_published_native_prose_preserves_candidates_and_unassessed_state(
    monkeypatch, capsys
):
    for uncertainty in [None, 2]:
        payload = {**CUSP}
        if uncertainty is not None:
            payload["birth_time_uncertainty_minutes"] = uncertainty
        result = call_surfaces(
            monkeypatch,
            capsys,
            "astro_india",
            payload,
            [
                "interpretation.vedic",
                "india.reading_basis",
            ],
        )
        text = result["interpretation"]["vedic"]
        assert "名义生时" in text["core_identity"]
        if uncertainty is None:
            assert "未提供" in text["uncertainty_note"]
            assert result["india"]["reading_basis"]["options_basis"] == "nominal_only"
        else:
            assert all(
                name in text["emotional_style"] for name in ["Magha", "Purva Phalguni"]
            )


def test_near_birth_partial_period_sampling_is_visible_across_surfaces(
    monkeypatch, capsys
):
    payload = {
        **CUSP,
        "birth_time_uncertainty_minutes": 2,
        "analysis_year": 1990,
        "analysis_month": 4,
        "analysis_day": 6,
        "analysis_hour": 15,
        "analysis_minute": 10,
    }
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        payload,
        [
            "vimshottari.birth_time_sensitivity",
            "summary",
        ],
    )
    context = result["vimshottari"]["birth_time_sensitivity"]
    assert (
        context["requested_sample_count"] == 9
        and context["evaluated_sample_count"] == 5
    )
    assert (
        context["omitted_samples"][0]["reason"] == "analysis_precedes_candidate_birth"
    )
    assert context["status"] == "partial_samples_before_analysis"
    assert len(context["omitted_samples"]) == 4
    assert context["endpoint_subset_requested_count"] == 3
    assert context["endpoint_subset_evaluated_count"] == 2


def test_intermediate_stage_and_matched_contexts_survive_three_surfaces(
    monkeypatch, capsys
):
    from tests.jyotish.test_jyotish_dasha_grid import BIRTH, TARGET

    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        {**BIRTH, **TARGET, "divisions": [30], "birth_time_uncertainty_minutes": 120},
        [
            "vimshottari.birth_time_sensitivity.stage_variants",
            "vimshottari.birth_time_sensitivity.requested_sample_count",
            "vimshottari.birth_time_sensitivity.adjacent_stage_change_brackets",
        ],
    )
    sensitivity = result["vimshottari"]["birth_time_sensitivity"]
    variant = next(
        v
        for v in sensitivity["stage_variants"]
        if (v["major_lord"], v["sub_lord"]) == ("Rahu", "Mars")
    )
    assert sensitivity["requested_sample_count"] == 481
    assert len(sensitivity["adjacent_stage_change_brackets"]) == 2
    assert variant["natal_ruler_contexts"]
    for context in variant["natal_ruler_contexts"]:
        assert context["sample_segments"]
        if context["chart"] == "D30":
            assert "longitude" not in context["sampled_numeric_ranges"]


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("projected", [False, True])
def test_declared_scope_and_nullable_pinda_on_all_surfaces(
    monkeypatch, capsys, key, projected
):
    payload = {**astro_payload(), "divisions": [], "birth_time_uncertainty_minutes": 1}
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    prefix = "india.ashtakavarga.charts.D1.reduction_analysis"
    fields = (
        [
            f"{prefix}.targets.Sun.sodhya_pinda",
            f"{prefix}.targets.Sun.status",
            f"{prefix}.occupancy_planets",
            f"{prefix}.method_id",
        ]
        if projected
        else [prefix, "india.birth_time_sensitivity"]
    )
    result = call_surfaces(monkeypatch, capsys, key, payload, fields)
    analysis = result["india"]["ashtakavarga"]["charts"]["D1"]["reduction_analysis"]
    assert analysis["method_id"] == METHOD
    assert analysis["occupancy_planets"] == list(PLANETS)
    if projected:
        assert set(analysis["targets"]) == {"Sun"}
        assert set(analysis["targets"]["Sun"]) == {"sodhya_pinda", "status"}
    else:
        assert analysis["source_id"] == SOURCE["id"]
        assert set(analysis["targets"]) == set(PLANETS)
        assert analysis["bhinna_fact_path"] == "india.ashtakavarga.charts.D1.bhinna"
        for row in analysis["targets"].values():
            if row["source_ambiguities"]:
                assert row["status"] == "partial_source_rule"
                assert row["sodhya_pinda"] is None
                assert row["rasi_pinda"] is None
            else:
                assert type(row["sodhya_pinda"]) is int
                assert row["sodhya_pinda"] == row["rasi_pinda"] + row["graha_pinda"]
        grid = result["india"]["birth_time_sensitivity"]["ashtakavarga_variants"]
        assert grid["sample_count"] == 5
        for variant in grid["charts"]["D1"]:
            assert "bhinna_fact_path" not in variant["reduction_analysis"]
            assert variant["reduction_analysis"]["method_id"] == METHOD
    assert "ashtakavarga_reductions" in describe_spec(SPECS[key])["evidence_views"]
    definitions = SPECS[key].output_model.model_json_schema()["$defs"]
    assert "PindaAnalysis" in definitions and "PindaRow" in definitions


def test_same_run_pinda_claims_retain_integer_null_and_reject_tampering():
    spec = SPECS["astro_india"]
    body = execute_tool(
        spec,
        spec.request_model.model_validate({**astro_payload(), "divisions": []}),
        options=ExecutionOptions(as_of=AS_OF),
    )
    meta = body["run_metadata"]
    analysis = body["india"]["ashtakavarga"]["charts"]["D1"]["reduction_analysis"]
    claims = []
    for planet, row in analysis["targets"].items():
        for field in ["rasi_pinda", "graha_pinda", "sodhya_pinda"]:
            claims.append(
                CalculationClaim(
                    path=f"india.ashtakavarga.charts.D1.reduction_analysis.targets.{planet}.{field}",
                    value=row[field],
                    run_id=meta["run_id"],
                    business_output_sha256=meta["business_output_sha256"],
                )
            )
    assert len(claims) == 21
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    bad = copy.deepcopy(claims)
    index = next((i for i, c in enumerate(bad) if c.value is None), 0)
    bad[index].value = 0 if bad[index].value is None else bad[index].value + 1
    assert verify_calculation_claims(body, bad)["status"] == "rejected"
