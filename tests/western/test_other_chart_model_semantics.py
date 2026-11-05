"""Real mean-node flag echoes, physical summaries and strict JPL pathways."""

import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import ephemeris
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.midpoints import PHYSICAL_BODIES, _native_factors
from fatebridge.core.astro.profiles import (
    ANALYTICAL_MEAN_NODE_MODEL,
    APPROXIMATE_ORBIT_MODEL,
    native_factor_model,
    physical_ephemeris_summary,
)
from fatebridge.core.fixed_stars import apparent_positions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.astrodice.test_astrodice_jpl import jpl as jpl

__all__ = ["jpl"]
pytestmark = pytest.mark.skipif(e.swe is None, reason="Swiss Ephemeris required")
BIRTH = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_timezone="UTC",
    birth_longitude=0,
    birth_latitude=0,
)


@pytest.fixture
def empty(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    directory = tmp_path / "empty"
    directory.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    e.configure_ephemeris_path()
    try:
        yield directory
    finally:
        monkeypatch.undo()
        e.configure_ephemeris_path(previous if previous is not None else "")


def test_real_mean_node_returns_identical_coordinates_with_three_source_bits(empty):
    coordinates, labels = [], []
    for requested in (e.swe.FLG_SWIEPH, e.swe.FLG_MOSEPH, e.swe.FLG_JPLEPH):
        values, returned = e.ephemeris_call(
            "calc", 2451545.0, e.swe.MEAN_NODE, requested | e.swe.FLG_SPEED
        )
        assert returned & requested
        coordinates.append(values)
        labels.append(e.ephemeris_model_from_retflag(returned))
        assert (
            native_factor_model(e.swe.MEAN_NODE, returned) == ANALYTICAL_MEAN_NODE_MODEL
        )
    assert coordinates[0] == coordinates[1] == coordinates[2]
    assert labels == ["swieph", "moshier", "jpl"]
    assert list(empty.iterdir()) == []  # no vector file could have supplied it


@pytest.mark.parametrize("sidereal", [False, True])
def test_node_does_not_make_a_moshier_chart_mixed(empty, sidereal):
    birth = build_astro_birth_info(**BIRTH)
    base = build_core_chart_payload(birth, "chart13", zodiacal=int(sidereal))
    profile = base["chart_profile"]
    assert profile["ephemeris_model"] == "moshier"
    assert profile["ephemeris_model_scope"] == "physical_bodies"
    assert profile["nonphysical_factor_models"] == {
        "North Node": ANALYTICAL_MEAN_NODE_MODEL
    }
    native = _native_factors(birth, sidereal, include_hypothetical=False)
    assert native["ephemeris_models"] == ["moshier"]
    node = next(p for p in native["factors"] if p["id"] == "North Node")
    assert node["model"] == ANALYTICAL_MEAN_NODE_MODEL
    assert node["native_return_flags"] & e.swe.FLG_SWIEPH
    assert set(native["physical_ephemeris_source"]["by_factor"]) == set(PHYSICAL_BODIES)


def test_physical_summary_still_preserves_real_mixing_and_failed_bodies():
    node = {"North Node": ANALYTICAL_MEAN_NODE_MODEL}
    assert (
        physical_ephemeris_summary({**node, "Sun": "swieph", "Moon": "moshier"})
        == "mixed"
    )
    assert (
        physical_ephemeris_summary(
            {**node, "Sun": "jpl", "Moon": APPROXIMATE_ORBIT_MODEL}
        )
        == "mixed"
    )
    assert (
        physical_ephemeris_summary({**node, "Sun": APPROXIMATE_ORBIT_MODEL}) == "none"
    )


def test_native_node_does_not_claim_a_physical_ephemeris_for_approximate_planets(
    empty, monkeypatch
):
    actual = ephemeris._swisseph_planet_state
    monkeypatch.setattr(
        ephemeris,
        "_swisseph_planet_state",
        lambda name, *a, **kw: actual(name, *a, **kw) if name == "North Node" else None,
    )
    profile = build_core_chart_payload(build_astro_birth_info(**BIRTH), "chart13")[
        "chart_profile"
    ]
    assert profile["engine_precision"] == "mixed_precision_runtime_model"
    assert profile["ephemeris_model"] == "none"
    assert profile["planetary_models"]["North Node"] == ANALYTICAL_MEAN_NODE_MODEL
    assert all(
        profile["planetary_models"][name] == APPROXIMATE_ORBIT_MODEL
        for name in PHYSICAL_BODIES
    )


@pytest.mark.parametrize("sidereal", [False, True])
@pytest.mark.parametrize("hypothetical", [False, True])
def test_native_hamburg_loop_honors_real_strict_jpl_kernel(jpl, sidereal, hypothetical):
    result = _native_factors(
        build_astro_birth_info(**BIRTH), sidereal, include_hypothetical=hypothetical
    )
    assert result["ephemeris_models"] == ["jpl"]
    assert result["ephemeris_model_scope"] == "physical_bodies"
    physical = result["physical_ephemeris_source"]
    assert set(physical["by_factor"]) == set(PHYSICAL_BODIES)
    assert all(row["model"] == "jpl" for row in physical["by_factor"].values())
    assert len(physical["files"]) == 1
    assert physical["files"][0]["de_number"] == 441
    assert physical["accuracy_certified"] is False
    node = next(p for p in result["factors"] if p["id"] == "North Node")
    assert node["model"] == ANALYTICAL_MEAN_NODE_MODEL
    assert node["native_return_flags"] & e.swe.FLG_JPLEPH


@pytest.mark.parametrize("sidereal", [False, True])
def test_fixed_star_observer_uses_jpl_and_restores_operator_configuration(
    jpl, sidereal
):
    selected = os.environ["SE_EPHE_PATH"]
    positions, profile = apparent_positions(2451545.0, sidereal=sidereal)
    assert len(positions) == 20 and profile["status"] == "computed"
    assert profile["earth_ephemeris_model"] == "jpl"
    assert profile["earth_flags"] & e.swe.FLG_JPLEPH
    assert all(row["native_flags"] & e.swe.FLG_JPLEPH for row in positions.values())
    assert os.environ["SE_EPHE_PATH"] == selected
    assert e.configured_ephemeris_path() == selected
    _, flags = e.ephemeris_call("calc", 2451545.0, e.swe.NEPTUNE, e.swe.FLG_SWIEPH)
    assert flags & e.swe.FLG_JPLEPH


@pytest.mark.parametrize("layer", ["hamburg", "stars"])
def test_out_of_range_strict_jpl_is_a_source_failure_in_both_layers(jpl, layer):
    selected = os.environ["SE_EPHE_PATH"]
    with pytest.raises(EphemerisSourceError):
        if layer == "hamburg":
            _native_factors(
                build_astro_birth_info(**{**BIRTH, "birth_year": 2005}), False
            )
        else:
            apparent_positions(2453372.5)
    assert os.environ["SE_EPHE_PATH"] == selected
    assert e.configured_ephemeris_path() == selected


@pytest.mark.parametrize(
    "key,variant",
    [
        ("astro_chart13", None),
        ("astro_chart", "chart13"),
        ("astro_germany", None),
        ("astro_chart", "germany"),
    ],
)
def test_model_semantics_cross_rest_mcp_cli(
    jpl, tmp_path, monkeypatch, capsys, key, variant
):
    spec = next(s for s in CATALOG if s.key == key)
    germany = key == "astro_germany" or variant == "germany"
    base = "base_chart.chart_profile" if germany else "chart_profile"
    fields = [base] + (
        ["midpoint_analysis.profile", "midpoint_analysis.factors"] if germany else []
    )
    payload = {**BIRTH, **({"chart_variant": variant} if variant else {})}
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2026-10-22T00:00:00Z",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    params = [("fields", name) for name in fields] + [
        (k, str(v).lower() if isinstance(v, bool) else str(v))
        for k, v in options.items()
        if k != "fields"
    ]
    response = TestClient(api.app).post(spec.rest_path, json=payload, params=params)
    assert response.status_code == 200
    rest = response.json()

    async def mcp():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    protocol = asyncio.run(mcp())
    assert not protocol.is_error
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))
    capsys.readouterr()
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
    assert code == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (rest, protocol.structured_content, cli):
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        profile = (result["base_chart"] if germany else result)["chart_profile"]
        assert profile["ephemeris_model"] == "jpl"
        assert profile["ephemeris_model_scope"] == "physical_bodies"
        assert profile["nonphysical_factor_models"] == {
            "North Node": ANALYTICAL_MEAN_NODE_MODEL
        }
        if germany:
            native = result["midpoint_analysis"]
            assert native["profile"]["ephemeris_models"] == ["jpl"]
            assert native["profile"]["ephemeris_model_scope"] == "physical_bodies"
            node = next(p for p in native["factors"] if p["id"] == "North Node")
            assert node["model"] == ANALYTICAL_MEAN_NODE_MODEL
            assert node["native_return_flags"] & e.swe.FLG_JPLEPH
