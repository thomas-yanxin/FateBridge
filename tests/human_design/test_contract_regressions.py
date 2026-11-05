"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import copy
import hashlib
import json
import math
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.cli import run
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.astro.time_scales import ephemeris_time, tt_from_ut1
from fatebridge.core.human_design import chart_at, chart_at_tt
from fatebridge.core.human_design_solar_projection import nominal_solar_projection
from fatebridge.core.human_design_time import epoch_context_at_tt
from fatebridge.mcp_server import create_mcp_app
from fatebridge.validation.human_design import verify_human_design_reading
from scripts.human_design.check_human_design_solar_projection import checks
from tests.support.ephemeris_context import moshier_ephemeris


def test_duplicate_page_locator_never_displaces_complete_receipt_provenance(
    tmp_path, monkeypatch
):
    store = delivery.ResultStore(tmp_path)
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    original = {
        "cycle_summary": {"reading": ""},
        "run_metadata": {
            "run_id": "same-original-run",
            "tool_name": "human_design",
            "provenance": {
                "method_id": ["source-bound-mechanics"],
                "record": "p" * 500,
            },
            "runtime": {
                "environment_sha256": "b" * 64,
                "ephemeris": {
                    "files": {f"reference-{i}.se1": "a" * 64 for i in range(120)},
                    "sha256": "c" * 64,
                },
            },
        },
    }
    # Fixed budget; vary only synthetic filler to exercise the actual boundary.
    prototype = delivery.bound_response(original, 8192)
    ref = {
        k: v
        for k, v in prototype["result_delivery"].items()
        if k
        not in ("available_fields", "total_bytes", "page_chars", "rest_manifest_path")
    }
    ref["compact_reference"] = True
    size = len(delivery._json({**prototype, "result_delivery": ref}))
    original["cycle_summary"]["reading"] = "中" * (8192 + 50 - size)
    before = copy.deepcopy(original)
    shaped = delivery.bound_response(original, 8192)
    ref = shaped["result_delivery"]
    assert len(delivery._json(shaped)) <= 8192
    assert ref["deferred_fields"] == ["run_metadata.runtime"]
    assert shaped["run_metadata"]["provenance"] == before["run_metadata"]["provenance"]
    assert shaped["cycle_summary"] == before["cycle_summary"]
    assert "first_page_uri" not in ref
    manifest = store.manifest(ref["result_id"])
    assert manifest["first_page_uri"] == ref["manifest_uri"] + "/pages/0"
    assert ref["sha256"] == manifest["sha256"]
    assert store.get(ref["result_id"]) == before == original
    file_record = json.loads(open(ref["file_path"]).read())
    assert file_record[ref["file_payload_path"]] == original


@pytest.mark.parametrize(
    "filename", ["swe_deltat.txt", "sedeltat.txt", "seleapsec.txt"]
)
def test_actual_child_auxiliary_change_keeps_safe_three_surface_source_error(
    tmp_path, monkeypatch, capsys, filename
):
    params = dict(
        birth_year=1900,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="UTC",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    original = native_execution._receive
    changes = []
    current = None

    def receive(*args):
        result = original(*args)
        if result.get("kind") == "ready":
            (current / filename).write_text(
                "# Auxiliary candidate created after worker ready\n"
            )
            changes.append(True)
        return result

    monkeypatch.setattr(native_execution, "_receive", receive)
    outputs = []
    current = tmp_path / "rest"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    with TestClient(api.app) as client:
        response = client.post("/api/astro/human-design", json=params)
    assert response.status_code == 503, response.text
    outputs.append(response.json())

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", params, raise_on_error=False
            )
            assert result.is_error
            return result.structured_content

    current = tmp_path / "mcp"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    outputs.append(asyncio.run(call()))
    current = tmp_path / "cli"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 1
    outputs.append(json.loads(capsys.readouterr().out))
    assert len(changes) == 3
    for result in outputs:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"][0]["code"] == "auxiliary_changed_during"
        assert str(tmp_path) not in json.dumps(result)


def test_same_run_pages_forbid_private_dispatch_as_well_as_parent_native_calls(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        delivery, "RESULT_STORE", delivery.ResultStore(tmp_path / "results")
    )

    async def check():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design",
                dict(
                    birth_year=1900,
                    birth_month=4,
                    birth_day=6,
                    birth_hour=9,
                    birth_minute=33,
                    birth_timezone="UTC",
                    birth_time_uncertainty_minutes=2,
                    fields=None,
                    include_snapshot_text=False,
                    response_char_limit=8192,
                ),
            )
            assert not result.is_error
            shaped = result.structured_content
            reference = shaped["result_delivery"]
            assert shaped["run_metadata"]["run_id"]

            def forbidden(*args, **kwargs):
                raise AssertionError(
                    "Paged original run cannot dispatch a private calculation or call native code"
                )

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(runtime, "ephemeris_call", forbidden)
                patch.setattr(native_execution, "calculate", forbidden)
                parts = []
                offset = 0
                while offset is not None:
                    page = json.loads(
                        (
                            await client.read_resource(
                                f"fatebridge://results/{reference['result_id']}/pages/{offset}"
                            )
                        )[0].text
                    )
                    parts.append(page["text"])
                    offset = page["next_offset"]
                text = "".join(parts)
                assert (
                    hashlib.sha256(text.encode()).hexdigest()
                    == reference["sha256"]
                    == page["sha256"]
                )
                original = json.loads(text)
                assert (
                    original["run_metadata"]["run_id"]
                    == shaped["run_metadata"]["run_id"]
                )
                verified = verify_human_design_reading(original)
                assert verified["status"] == "verified_fixed_template_reading", verified
                assert (
                    original["native_execution_context"]["mechanism"]
                    == "fresh_exec_process"
                )

    asyncio.run(check())


def test_all21600_frozen_geometric_inputs_without_narrowing_the_cohort():
    report = checks()
    assert report["case_count"] == report["cases_matched"] == 21600
    assert report["failures"] == []
    assert len(report["inside_nominal_projection_cases"]) == 7
    assert report["native_astronomy_accuracy_certified"] is False
    assert report["physical_occultation_certified"] is False
    assert report["visibility_certified"] is False


def test_same_projection_does_not_confuse_foreground_and_background():
    front = nominal_solar_projection([0, 0, 1], [0, 0, 0.01])
    behind = nominal_solar_projection([0, 0, 1], [0, 0, 2])
    assert front["inside_nominal_solar_disk_projection"] is True
    assert behind["inside_nominal_solar_disk_projection"] is True
    assert front["more_distant_than_sun_in_supplied_coordinates"] is False
    assert behind["more_distant_than_sun_in_supplied_coordinates"] is True
    assert behind["visibility_certified"] is False


def test_nominal_limb_is_reported_as_a_numerical_boundary_not_a_physical_fact():
    radius = nominal_solar_projection([0, 0, 1], [0, 0, 2])[
        "nominal_solar_radius_radians"
    ]
    result = nominal_solar_projection([0, 0, 1], [math.degrees(radius), 0, 2])
    assert result["projection_relation"] == "numerical_boundary_undetermined"
    assert result["inside_nominal_solar_disk_projection"] is None
    assert result["physical_accuracy_certified"] is False


def test_nonzero_solar_latitude_and_antipodal_direction_are_not_flattened():
    result = nominal_solar_projection([0, 30, 1], [0, -30, 2])
    assert abs(result["separation_radians"] - math.pi / 3) < 1e-12
    opposite = nominal_solar_projection([0, 0, 1], [180, 0, 2])
    assert opposite["separation_radians"] == math.pi
    assert opposite["inside_nominal_solar_disk_projection"] is False


@pytest.mark.parametrize(
    "coordinates",
    [[0, 0], [0, float("nan"), 1], [0, 91, 1], [0, 0, 0], [True, 0, 1]],
)
def test_missing_or_invalid_geometry_is_not_filled_with_defaults(coordinates):
    with pytest.raises(ValueError):
        nominal_solar_projection([0, 0, 1], coordinates)


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize(
    "year", [1800, 1850, 1900, 1955, 1959, 1960, 1961, 1965, 1972, 2000, 2399]
)
def test_epoch_ut1_is_the_inverse_of_the_declared_forward_policy(year, empty_files):
    def check():
        moment = datetime(year, 1, 1, 12, tzinfo=timezone.utc)
        forward = ephemeris_time(moment)
        context = epoch_context_at_tt(forward.jd_tt, method="test")["time"]
        assert context["jd_tt"] == forward.jd_tt
        assert context["jd_ut1"] == forward.jd_ut1
        assert tt_from_ut1(context["jd_ut1"]) == forward.jd_tt

    if empty_files:
        with moshier_ephemeris():
            check()
    else:
        check()


@pytest.mark.parametrize("year", [1800, 1900, 1959, 1960, 1965, 2000])
def test_tt_sampler_and_design_context_round_trip_without_changing_the_chart(year):
    moment = datetime(year, 4, 6, 1, 33, tzinfo=timezone.utc)
    civil = chart_at(moment)
    sampled = chart_at_tt(civil["time_scales"]["personality"]["jd_tt"])
    assert sampled["time_scales"]["personality"]["jd_ut1"] == (
        civil["time_scales"]["personality"]["jd_ut1"]
    )
    for side in ("personality", "design"):
        context = sampled["time_scales"][side]
        assert tt_from_ut1(context["jd_ut1"]) == context["jd_tt"]
    for field in ("activations", "bodygraph", "profile", "variables"):
        assert civil[field] == sampled[field]
    # datetime inversion can round a civil label by microseconds; it must not
    # move the physical TT root or its numerical convergence diagnostics.
    assert {
        k: v for k, v in civil["design_solver"].items() if k != "civil_elapsed_days"
    } == {
        k: v for k, v in sampled["design_solver"].items() if k != "civil_elapsed_days"
    }
    assert (
        abs(
            civil["design_solver"]["civil_elapsed_days"]
            - sampled["design_solver"]["civil_elapsed_days"]
        )
        * 86400
        <= 0.0002
    )


@pytest.mark.parametrize("year,expected_flag", [(1800, -1), (1965, 2)])
def test_epoch_context_obeys_the_shared_historical_delta_t_flag(
    monkeypatch, year, expected_flag
):
    # A controlled model makes this regression independent of installed files.
    # The old copied SWIEPH loop incorrectly used flag 2 before the UTC era.
    moment = datetime(year, 6, 1, tzinfo=timezone.utc)
    tt = ephemeris_time(moment).jd_tt
    monkeypatch.setattr(
        "fatebridge.core.human_design_time.utc_from_tt",
        lambda jd: (moment.isoformat(), moment, False),
    )
    flags = []

    def delta_t(operation, jd, flag):
        assert operation == "deltat_ex"
        flags.append(flag)
        return (60 if flag == -1 else 61) / 86400

    monkeypatch.setattr(runtime, "ephemeris_call", delta_t)
    result = epoch_context_at_tt(tt, method="test")["time"]
    assert flags == [expected_flag] * 4
    assert result["jd_ut1"] == tt - (60 if year < 1960 else 61) / 86400
