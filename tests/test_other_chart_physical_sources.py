"""Actual Swiss file contexts, analytical fallback, and source-coherent grids."""

import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from fatebridge.core.astro.midpoints import PHYSICAL_BODIES, _native_factors
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    PhysicalSourceCohort,
)
from fatebridge.core.astro.sensitivity import time_sensitivity
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.utils.errors import EphemerisSourceError

pytestmark = pytest.mark.skipif(e.swe is None, reason="Swiss Ephemeris required")


@pytest.fixture(autouse=True)
def restore_configuration(monkeypatch):
    previous = e.configured_ephemeris_path()
    previous_env = os.environ.get("SE_EPHE_PATH")
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    yield
    if previous_env is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", previous_env)
    e.configure_ephemeris_path(previous if previous is not None else "")


@pytest.fixture
def ephemeris_files(tmp_path):
    source = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_DIR",
            str(Path(__file__).resolve().parents[1] / "ephe"),
        )
    )
    manifest = load_ephemeris_manifest()
    for name in ("sepl_18.se1", "semo_18.se1", "sepl_24.se1", "semo_24.se1"):
        if not (source / name).is_file():
            pytest.fail(
                "This integration test requires separately acquired, pinned Swiss files: "
                "uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 1800 2500"
            )
        verify_ephemeris_bytes(name, (source / name).read_bytes(), manifest)
    target = tmp_path / "ephe"
    target.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        shutil.copy2(source / name, target / name)
        # Frozen integration inputs are read-only. Only private disposable
        # copies may be mutated by the file-change regression on every OS.
        (target / name).chmod(0o644)
    return source, target


def birth(moment=None):
    if moment is None:
        return build_astro_birth_info(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_timezone="UTC",
            birth_longitude=0,
            birth_latitude=0,
        )
    return build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )


def edge_birth(directory):
    e.configure_ephemeris_path(str(directory))
    e.ephemeris_call("calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH)
    # This is a data-coverage regression, not an independent astronomical epoch.
    edge = e.swe.get_current_file_data(0)[2]
    return birth(datetime_from_tt(edge))


def test_actual_se1_headers_hashes_and_factor_references(ephemeris_files):
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    result = _native_factors(birth(), False, include_hypothetical=False)
    source = result["physical_ephemeris_source"]
    assert set(source["by_factor"]) == set(PHYSICAL_BODIES)
    assert {f["filename"] for f in source["files"]} == {"sepl_18.se1", "semo_18.se1"}
    ids = {f["id"] for f in source["files"]}
    for row in source["files"]:
        path, start, end, de_number = e.swe.get_current_file_data(row["slot"])
        assert row["filename"] == Path(path).name
        assert row["sha256"] == hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert (
            row["start_julian_day_tt"],
            row["end_julian_day_tt"],
            row["de_number"],
        ) == (start, end, de_number)
        assert row["matches_packaged_manifest"] is True
        assert row["de_number"] > 0
    for row in source["by_factor"].values():
        assert row["model"] == "swieph"
        assert row["status"] == "se1_contexts_observed"
        assert row["file_ids"] and set(row["file_ids"]) <= ids
    assert str(directory) not in json.dumps(source)
    assert source["atomic_file_read_proven"] is False
    assert source["accuracy_certified"] is False


def test_analytical_fallback_never_claims_stale_file_contexts(ephemeris_files):
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    e.ephemeris_call("calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH)
    assert e.swe.get_current_file_data(0)[0]
    e.ephemeris_call("calc", 2451545.0, e.swe.NEPTUNE, e.swe.FLG_MOSEPH)
    trace = PhysicalEphemerisTrace()
    trace.observe("Neptune", "moshier")
    result = trace.finish()
    assert result["files"] == []
    assert result["by_factor"]["Neptune"] == {
        "model": "moshier",
        "status": "library_builtin",
        "file_ids": [],
    }


def test_missing_file_introspection_is_unavailable_not_invented(monkeypatch):
    monkeypatch.delattr(e.swe, "get_current_file_data")
    trace = PhysicalEphemerisTrace()
    trace.observe("Sun", "swieph")
    source = trace.finish()
    assert source["files"] == []
    assert source["by_factor"]["Sun"]["status"] == "identity_unavailable"
    assert source["has_unidentified_sources"] is True


def test_file_mutation_after_first_observation_is_rejected(
    ephemeris_files, monkeypatch
):
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    original = e.swe.calc

    def mutate_after_moon(*args, **kwargs):
        value = original(*args, **kwargs)
        if args[1] == e.swe.MOON:
            path = directory / "sepl_18.se1"
            path.write_bytes(path.read_bytes() + b"changed-after-first-observation")
        return value

    monkeypatch.setattr(e.swe, "calc", mutate_after_moon)
    with pytest.raises(ValueError, match="Physical ephemeris file changed during"):
        _native_factors(birth(), False, include_hypothetical=False)


def test_real_partial_coverage_cannot_be_called_pure_time_sensitivity(ephemeris_files):
    _, directory = ephemeris_files
    center = edge_birth(directory)
    with pytest.raises(
        EphemerisSourceError, match="Physical ephemeris model changed across"
    ):
        time_sensitivity(
            center, sidereal=False, uncertainty_minutes=1, include_hypothetical=False
        )


def test_complete_adjacent_segments_preserve_the_whole_declared_interval(
    ephemeris_files,
):
    source, directory = ephemeris_files
    center = edge_birth(directory)
    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(source / name, directory / name)
    result = time_sensitivity(
        center, sidereal=False, uncertainty_minutes=1, include_hypothetical=False
    )
    assert result["status"] == "sampled" and result["sample_count"] == 5
    assert result["physical_ephemeris_models_consistent"] is True
    assert result["represented_radius_seconds"] == 60
    contexts = result["physical_ephemeris_sources"]
    assert len(contexts) >= 2
    assert {r["filename"] for s in contexts for r in s["files"]} >= {
        "sepl_18.se1",
        "sepl_24.se1",
    }
    for sample in result["samples"]:
        assert all(
            r["model"] == "swieph"
            for r in contexts[sample["physical_source_index"]]["by_factor"].values()
        )


def sample_source():
    return {
        "by_factor": {"Sun": {"model": "swieph"}, "Moon": {"model": "moshier"}},
        "files": [
            {"slot": 0, "filename": "sepl_18.se1", "sha256": "a" * 64, "de_number": 441}
        ],
    }


def test_per_factor_model_swaps_are_detected_even_if_aggregate_set_is_equal():
    first = sample_source()
    second = copy.deepcopy(first)
    second["by_factor"] = {"Sun": {"model": "moshier"}, "Moon": {"model": "swieph"}}
    assert {r["model"] for r in first["by_factor"].values()} == {
        r["model"] for r in second["by_factor"].values()
    }
    cohort = PhysicalSourceCohort()
    cohort.add(first)
    with pytest.raises(ValueError, match="model changed across"):
        cohort.add(second)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("de_number", 431, "DE header editions"),
        ("sha256", "b" * 64, "file changed across"),
    ],
)
def test_same_model_label_cannot_hide_changed_data(field, value, message):
    first = sample_source()
    second = copy.deepcopy(first)
    second["files"][0][field] = value
    cohort = PhysicalSourceCohort()
    cohort.add(first)
    with pytest.raises(ValueError, match=message):
        cohort.add(second)


def test_adjacent_segment_with_the_same_edition_is_allowed():
    first = sample_source()
    second = copy.deepcopy(first)
    second["files"][0].update(filename="sepl_24.se1", sha256="b" * 64)
    cohort = PhysicalSourceCohort()
    assert cohort.add(first) == 0
    assert cohort.add(second) == 1
    assert cohort.add(copy.deepcopy(second)) == 1


def test_nominal_and_sampled_models_must_also_agree(monkeypatch):
    from fatebridge.core.astro import sensitivity

    first = sample_source()
    second = copy.deepcopy(first)
    second["by_factor"]["Sun"]["model"] = "moshier"
    monkeypatch.setattr(
        sensitivity,
        "time_sensitivity",
        lambda *args, **kwargs: {
            "status": "sampled",
            "hypothetical_element_source": {},
            "physical_ephemeris_sources": [second],
        },
    )
    payload = {
        "base_chart": {"chart_profile": {"zodiac": "tropical"}},
        "midpoint_analysis": {
            "profile": {
                "hypothetical_element_source": {},
                "physical_ephemeris_source": first,
            }
        },
    }
    with pytest.raises(ValueError, match="model changed across"):
        sensitivity.enrich_specialty_sensitivity(
            payload, birth(), kind="germany", uncertainty_minutes=1
        )


@pytest.mark.parametrize(
    "key,variant",
    [
        ("astro_germany", None),
        ("astro_chart", "germany"),
        ("astro_chart13", None),
        ("astro_chart", "chart13"),
    ],
)
def test_partial_data_error_and_complete_interval_across_three_surfaces(
    ephemeris_files, monkeypatch, tmp_path, capsys, key, variant
):
    import asyncio

    from fastapi.testclient import TestClient
    from fastmcp import Client

    import fatebridge.api as api
    from fatebridge.cli import run
    from fatebridge.mcp_server import create_mcp_app
    from fatebridge.services.tool_catalog import CATALOG

    source, directory = ephemeris_files
    center = edge_birth(directory).utc_datetime
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    payload = {
        "name": "虚构：星历覆盖边界",
        "birth_year": center.year,
        "birth_month": center.month,
        "birth_day": center.day,
        "birth_hour": center.hour,
        "birth_minute": center.minute,
        "birth_second": center.second,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "birth_time_uncertainty_minutes": 1.0,
    }
    if variant:
        payload["chart_variant"] = variant
    spec = next(s for s in CATALOG if s.key == key)
    path = (
        "midpoint_analysis.time_sensitivity"
        if key == "astro_germany" or variant == "germany"
        else "time_sensitivity"
    )
    options = {
        "fields": [path],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
        "as_of": "2026-10-22T00:00:00Z",
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    request = tmp_path / "coverage-request.json"
    request.write_text(json.dumps(payload))

    def surfaces():
        params = [("fields", path)] + [
            (k, str(v).lower() if isinstance(v, bool) else str(v))
            for k, v in options.items()
            if k != "fields"
        ]
        rest = TestClient(api.app).post(spec.rest_path, json=payload, params=params)

        async def mcp():
            async with Client(create_mcp_app()) as client:
                return await client.call_tool(
                    spec.tool_name, {**payload, **options}, raise_on_error=False
                )

        protocol = asyncio.run(mcp())
        capsys.readouterr()
        code = run(
            [
                spec.tool_name,
                "--subject-file",
                str(request),
                "--fields",
                path,
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
                "--as-of",
                options["as_of"],
            ]
        )
        cli = json.loads(capsys.readouterr().out)
        return rest, protocol, code, cli

    rest, protocol, code, cli = surfaces()
    assert rest.status_code == 503 and protocol.is_error and code == 1
    for error in (rest.json(), json.loads(protocol.content[0].text), cli):
        assert error["error_code"] == "ephemeris_source_inconsistent"
        assert "Physical ephemeris model changed across" in error["error"]
        assert error["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "model_changed"}
        ]
        assert error["retryable"] is False
        assert str(directory) not in json.dumps(error)

    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(source / name, directory / name)
    e.configure_ephemeris_path(str(directory))
    rest, protocol, code, cli = surfaces()
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    bodies = [rest.json(), protocol.structured_content, cli]
    sensitivities = []
    for body in bodies:
        for component in path.split("."):
            body = body[component]
        sensitivities.append(body)
    assert sensitivities[0] == sensitivities[1] == sensitivities[2]
    assert sensitivities[0]["sample_count"] == 5
    assert sensitivities[0]["represented_radius_seconds"] == 60
