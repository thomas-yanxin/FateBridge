"""Original orbital states, retained controls and real historical consumers."""

import asyncio
import gzip
import hashlib
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core import de440_solar
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.fengshui import historical_solar
from fatebridge.core.fengshui.calendar import (
    boundary_uncertainty_reason,
    lichun,
    lichun_resolution,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.utils.errors import EphemerisSourceError
from tests.fengshui.test_fengshui_surfaces import rest_client, without_transport

ROOT = Path(__file__).parents[2]
FOLDER = ROOT / "tests/data/fengshui_historical_solar_v1"
PROTOCOL = json.loads((FOLDER / "protocol.json").read_text())
DATA = ROOT / "src/fatebridge/data/astronomy"
MODEL = de440_solar.HISTORICAL_MODEL_ID
REFERENCE = json.loads(
    (ROOT / "tests/data/fengshui_lichun_tt/reference.json").read_text()
)


def test_all_original_state_rows_and_predeclared_tolerances():
    hashes = json.loads((FOLDER / "hashes.json").read_text())
    for name, expected in hashes.items():
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == expected
    assert PROTOCOL["software_years"] == [1784, 2204]
    assert PROTOCOL["tt_crossing_tolerance_seconds"] == 1.0
    states = json.loads(gzip.decompress((FOLDER / "states.json.gz").read_bytes()))
    assert states["state_rows"] == len(states["rows"]) == 5052
    assert states["epochs"] == len({r["tdb_jd"] for r in states["rows"]}) == 1684
    assert states["independent_evaluator"] == "jplephem2.24 original full SPK"
    assert (
        len({(r["center"], r["target"], r["tdb_jd"]) for r in states["rows"]}) == 5052
    )
    for row in states["rows"]:
        position, velocity = de440_solar.state(
            (row["center"], row["target"]),
            row["tdb_jd"] - 2451545.0,
            profile_id=MODEL,
        )
        assert max(abs(a - b) for a, b in zip(position, row["position_km"])) <= (
            PROTOCOL["state_sampling"]["position_tolerance_km"]
        )
        assert max(
            abs(a - b) for a, b in zip(velocity, row["velocity_km_per_day"])
        ) <= (PROTOCOL["state_sampling"]["velocity_tolerance_km_per_day"])


def test_original_profile_bytes_and_overlapping_states_are_unchanged():
    for name, expected in PROTOCOL["preserve_base_profile"]["files"].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == expected
    rows = json.loads(gzip.decompress((FOLDER / "states.json.gz").read_bytes()))["rows"]
    checked = 0
    for row in rows:
        epoch = row["tdb_jd"]
        if (
            date(1800, 1, 1).toordinal() + 1721424.5
            <= epoch
            < date(2201, 1, 1).toordinal() + 1721424.5
        ):
            pair = (row["center"], row["target"])
            assert de440_solar.state(pair, epoch - 2451545.0) == de440_solar.state(
                pair, epoch - 2451545.0, profile_id=MODEL
            )
            checked += 1
    assert checked == 4812
    assert de440_solar.source_receipt()["model_id"] == de440_solar.MODEL_ID


@pytest.mark.parametrize("mode", ["auto", "de440"])
@pytest.mark.parametrize("year", [1784, 1785, 1799, 2201, 2204])
def test_both_selected_packaged_modes_identify_the_actual_historical_source(
    monkeypatch, mode, year
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    result = lichun_resolution(year, "Asia/Shanghai")
    assert result["ephemeris_model"] == MODEL
    assert result["provider"] == "jpl_de440" and result["approximate"] is False
    details = result["solar_model_details"]
    assert details["reference_event_table_used"] is False
    assert details["selected_civil_year"] == year
    assert details["software_solar_term_years"] == [1784, 2204]
    assert details["source_kernel_sha256"] == PROTOCOL["source_kernel"]["sha256"]
    assert details["coefficient_manifest_sha256"] == (
        "d7cf5e3ee5bda32b54bbbf087dedff62d0c4f7ea64824e64ccfe572fe879bda0"
    )
    root = datetime.fromisoformat(result["moment"])
    assert lichun(year, "Asia/Shanghai") == root
    assert root == datetime.fromisoformat(lichun_resolution(year, "UTC")["moment"])
    assert boundary_uncertainty_reason(root + timedelta(seconds=5), result) == (
        "de440_historical_solar_model_guard_not_accuracy_certification"
    )
    assert boundary_uncertainty_reason(root + timedelta(seconds=6), result) is None


@pytest.mark.parametrize("year", [1783, 1800, 2000, 2200, 2205])
def test_other_years_do_not_open_the_historical_profile(monkeypatch, year):
    def unavailable(*args, **kwargs):
        pytest.fail("An unused historical source must not be loaded")

    monkeypatch.setattr(de440_solar, "cache_key", unavailable)
    assert historical_solar.historical_solar_resolution(year, "立春", "UTC") is None


@pytest.mark.parametrize("mode", ["native", "analytic", "spk"])
def test_explicit_other_models_are_not_replaced(monkeypatch, mode):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    assert historical_solar.historical_solar_resolution(1785, "立春", "UTC") is None


def test_strict_jpl_auto_selection_is_not_replaced(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de441.eph")
    assert historical_solar.historical_solar_resolution(1785, "立春", "UTC") is None


def test_1785_raw_numeric_failure_is_fixed_and_native_control_is_retained(
    monkeypatch, tmp_path
):
    reference = next(r for r in REFERENCE["rows"] if r["year"] == 1785)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    corrected = lichun_resolution(1785, "UTC")
    difference = (
        ephemeris_time(datetime.fromisoformat(corrected["moment"])).jd_tt
        - reference["jd_tt"]
    ) * 86400
    assert (
        abs(difference)
        <= REFERENCE["protocol"]["numeric_implementation_tolerance_seconds"]
    )
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    native = lichun_resolution(1785, "UTC")
    assert native["ephemeris_model"] == "moshier"
    old_difference = (
        ephemeris_time(datetime.fromisoformat(native["moment"])).jd_tt
        - reference["jd_tt"]
    ) * 86400
    assert abs(old_difference) > 1.0


@pytest.mark.parametrize("changed_mode", ["native", "invalid_during_solar_batch"])
def test_configuration_changes_during_a_root_are_not_delivered(
    monkeypatch, changed_mode
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    original = de440_solar.longitude_crossing_tt

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", changed_mode)
        return result

    monkeypatch.setattr(de440_solar, "longitude_crossing_tt", changed)
    with pytest.raises(EphemerisSourceError, match="configuration changed"):
        lichun_resolution(1785, "UTC")


@pytest.mark.parametrize(
    "fault", ["missing", "bytes", "tdb_identity", "model_identity"]
)
def test_corrupt_historical_data_fail_without_a_native_fallback(
    monkeypatch, tmp_path, fault
):
    folder = tmp_path / "data/astronomy"
    folder.mkdir(parents=True)
    for name in (
        "de440-solar-historical-v1.json",
        "de440-solar-historical-v1.bin.gz",
        "geocentric-tdb-v1.json",
    ):
        shutil.copyfile(DATA / name, folder / name)
    metadata = folder / "de440-solar-historical-v1.json"
    if fault == "missing":
        (folder / "de440-solar-historical-v1.bin.gz").unlink()
    elif fault == "bytes":
        (folder / "de440-solar-historical-v1.bin.gz").write_bytes(b"invalid")
    else:
        info = json.loads(metadata.read_text())
        info["tdb_coefficient_sha256" if fault == "tdb_identity" else "model_id"] = (
            "changed"
        )
        metadata.write_text(json.dumps(info))
    de440_solar._profile.cache_clear()
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    try:
        monkeypatch.setattr(de440_solar, "files", lambda _: tmp_path)
        with pytest.raises(EphemerisSourceError, match="coefficients"):
            lichun_resolution(1785, "UTC")
    finally:
        de440_solar._profile.cache_clear()


@pytest.mark.parametrize("year,expected_period", [(1800, 6), (2199, 8)])
def test_actual_period_endpoints_keep_the_source_on_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, year, expected_period
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    data = {
        "house": {"facing_degrees": 180, "north_reference": "magnetic"},
        "period": {
            "basis": "construction_completion",
            "effective_event_year": year,
            "evidence": "Synthetic historical source regression, not a property",
        },
    }

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_xuankong_natal", {**data, "response_char_limit": 0}
            )

    http = rest_client(monkeypatch).post("/api/fengshui/xuankong_natal", json=data)
    mcp = asyncio.run(call())
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    code = run(["fengshui_xuankong_natal", "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not mcp.is_error and code == 0
    assert (
        without_transport(http.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    period = cli["layers"]["xuankong_natal"]["period_context"]
    assert period["number"] == expected_period
    endpoints = [period["timing"]["start"], period["timing"]["end"]]
    assert any(r["ephemeris_model"] == MODEL for r in endpoints)
    assert MODEL in cli["run_metadata"]["provenance"]["ephemeris_model"]


@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_de440_candidate_guard_is_not_called_a_linear_fallback_on_any_protocol(
    monkeypatch, tmp_path, capsys, name
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    # An internally computed instant checks candidate semantics only. Absolute
    # TT accuracy is checked separately against the unchanged external table.
    event = lichun(2024, "UTC").isoformat()
    inputs = {
        "house": {"facing_degrees": 180, "north_reference": "magnetic"},
        "period": {
            "basis": "first_occupancy",
            "event_at": event,
            "evidence": "Synthetic computed boundary, not a property event",
        },
    }
    if name == "assess":
        inputs = {"methods": ["xuankong_natal"], "xuankong": inputs}

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_" + name, {**inputs, "response_char_limit": 0}
            )

    http = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    mcp = asyncio.run(call())
    path = tmp_path / "boundary.json"
    path.write_text(json.dumps(inputs))
    code = run(["fengshui_" + name, "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not mcp.is_error and code == 0
    assert (
        without_transport(http.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    context = cli["layers"]["xuankong_natal"]["period_context"]
    assert context["number"] is None and context["candidate_period_numbers"] == [8, 9]
    assert (
        context["confirmation_reason"]
        == "de440_solar_model_precision_guard_in_period_changeover_year"
    )
    assert context["timing"]["event_year_boundary"]["approximate"] is False
    assert "交节采用DE440轨道计算" in cli["snapshot_text"]
    assert "交节采用近似回退" not in cli["snapshot_text"]


def test_missing_historical_source_cannot_be_hidden_by_projection_on_any_protocol(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    original = de440_solar._selected_profile

    def unavailable(profile_id):
        if profile_id == MODEL:
            raise EphemerisSourceError("solar_de440_invalid")
        return original(profile_id)

    monkeypatch.setattr(de440_solar, "_selected_profile", unavailable)
    inputs = {
        "house": {"facing_degrees": 180, "north_reference": "magnetic"},
        "period": {
            "basis": "construction_completion",
            "effective_event_year": 1800,
            "evidence": "Synthetic source failure, not property evidence",
        },
    }

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_xuankong_natal",
                {**inputs, "fields": ["status"], "strict_fields": True},
                raise_on_error=False,
            )

    http = rest_client(monkeypatch).post(
        "/api/fengshui/xuankong_natal",
        json=inputs,
        params={"fields": "status", "strict_fields": "true"},
    )
    mcp = asyncio.run(call())
    path = tmp_path / "missing-source.json"
    path.write_text(json.dumps(inputs))
    code = run(
        [
            "fengshui_xuankong_natal",
            "--request-file",
            str(path),
            "--fields",
            "status",
            "--strict-fields",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 503 and mcp.is_error and code == 1
    assert (
        http.json()["error_code"]
        == cli["error_code"]
        == "ephemeris_source_inconsistent"
    )
    assert "layers" not in cli and "snapshot_text" not in cli
