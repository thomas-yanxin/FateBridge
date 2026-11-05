"""Default orbit data, exact old counterexamples, and three public protocols."""

import asyncio
import json
import shutil
from datetime import date, datetime
from pathlib import Path

import pytest

from fatebridge.core import almanac, de440_solar
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.test_agentic_nested_outputs import rest as _shared_rest
from tests.test_bazi_year_contract import TOPICS

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/fatebridge/data/astronomy"


@pytest.fixture
def default_without_external_files(monkeypatch, tmp_path):
    previous = configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    for env in [
        "FATEBRIDGE_JPL_FILE",
        "FATEBRIDGE_SOLAR_TERM_MODEL",
        "FATEBRIDGE_SOLAR_SPK_FILE",
    ]:
        monkeypatch.delenv(env, raising=False)
    try:
        yield
    finally:
        monkeypatch.undo()
        configure_ephemeris_path(previous)


def test_packaged_profile_is_orbital_data_with_declared_time_and_frame():
    receipt = de440_solar.source_receipt()
    assert receipt["model_id"] == de440_solar.MODEL_ID
    assert receipt["source_kernel_sha256"] == (
        "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
    )
    assert receipt["reference_event_table_used"] is False
    assert receipt["spk_frame_id"] == 1
    assert receipt["accuracy_certified"] is False
    assert set(receipt["segment_coverage_tdb_jd"]) == {"0->3", "3->399", "0->10"}
    assert receipt["tdb_model_author_comparison_years"] == [1950, 2050]
    for start, end in receipt["segment_coverage_tdb_jd"].values():
        assert start <= date(1798, 1, 1).toordinal() + 1721424.5
        assert end >= date(2203, 1, 1).toordinal() + 1721424.5


def test_packaged_profile_receipt_does_not_expose_mutable_loaded_metadata():
    first = de440_solar.source_receipt()
    original = first["segment_coverage_tdb_jd"]["0->3"][0]
    first["segment_coverage_tdb_jd"]["0->3"][0] = -1
    first["tdb_model_author_comparison_years"].clear()
    second = de440_solar.source_receipt()
    assert second["segment_coverage_tdb_jd"]["0->3"][0] == original
    assert second["tdb_model_author_comparison_years"] == [1950, 2050]
    assert de440_solar.cache_key()[0] == second["coefficient_manifest_sha256"]


@pytest.mark.parametrize("fault", ["missing", "bytes", "frame", "tdb_nan"])
def test_packaged_profile_corruption_is_a_source_error(monkeypatch, tmp_path, fault):
    folder = tmp_path / "data/astronomy"
    folder.mkdir(parents=True)
    for name in [
        "de440-solar-v1.json",
        "de440-solar-v1.bin.gz",
        "geocentric-tdb-v1.json",
    ]:
        shutil.copyfile(DATA / name, folder / name)
    if fault == "missing":
        (folder / "de440-solar-v1.bin.gz").unlink()
    elif fault == "bytes":
        path = folder / "de440-solar-v1.bin.gz"
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 1
        path.write_bytes(raw)
    elif fault == "frame":
        path = folder / "de440-solar-v1.json"
        data = json.loads(path.read_text())
        data["segments"][0]["frame"] = 17
        path.write_text(json.dumps(data))
    else:
        path = folder / "geocentric-tdb-v1.json"
        data = json.loads(path.read_text())
        data["fairhead_terms"][0][0] = float("nan")
        path.write_text(json.dumps(data))
    de440_solar._profile.cache_clear()
    with monkeypatch.context() as context:
        context.setattr(de440_solar, "files", lambda _: tmp_path)
        try:
            with pytest.raises(EphemerisSourceError, match="coefficients"):
                de440_solar.source_receipt()
        finally:
            de440_solar._profile.cache_clear()


def test_out_of_coverage_and_nonfinite_points_do_not_receive_an_approximation():
    for pair in [(0, 3), (3, 399), (0, 10)]:
        for epoch in [-1000000, 1000000]:
            with pytest.raises(EphemerisSourceError, match="cover"):
                de440_solar.state(pair, epoch)
        with pytest.raises(ValueError, match="finite"):
            de440_solar.state(pair, float("nan"))
    with pytest.raises(ValueError, match="finite"):
        de440_solar.geocentric_tdb_minus_tt(float("inf"))


def test_default_corrects_all_five_analytic_and_the_swiss_term_counterexamples(
    default_without_external_files,
):
    probes = json.loads(
        (ROOT / "tests/data/bazi_boundary_decisions_v1/probes.json").read_text()
    )["rows"]
    identifiers = [
        "1922-清明-floor",
        "1964-惊蛰-floor",
        "1975-芒种-floor",
        "1980-夏至-floor",
        "2022-小暑-floor",
        "1936-雨水-next_minute",
    ]
    for identifier in identifiers:
        row = next(r for r in probes if r["id"] == identifier)
        moment = datetime.fromisoformat(row["civil_utc"])
        expected = row["reference_state_under_frozen_policy"]
        current, following = almanac.get_adjacent_solar_terms(moment, "UTC")
        assert current.name == expected["last_term"]
        assert following.name == expected["next_term"]
        assert (
            almanac.get_bazi_month_context(moment, "UTC")["branch"]
            == expected["month_branch"]
        )
        assert (
            BaZiCalendar.get_four_pillars(moment, "UTC")["month"][1]
            == expected["month_branch"]
        )
        for term in [current, following]:
            assert term.ephemeris_model == de440_solar.MODEL_ID
            assert term.resolution_provider == "jpl_de440"
            assert term.ephemeris_retflags == ()


def test_default_orbit_source_does_not_probe_an_unused_native_sun(
    default_without_external_files,
    monkeypatch,
):
    def unused(*args, **kwargs):
        raise AssertionError("Unused native Sun solver was called")

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", unused)
    terms = almanac.get_solar_terms_for_year(2033, "UTC")
    assert len(terms) == 24
    assert all(t.resolution_provider == "jpl_de440" for t in terms)


@pytest.mark.parametrize(
    "key",
    ["bazi_" + topic for topic in TOPICS]
    + [
        "liuyue_analysis",
        "liuri_analysis",
        "liushi_analysis",
        "sixyao",
        "liureng_gods",
        "jinkou",
    ],
)
def test_default_de440_is_consumed_identically_by_three_protocols(
    key,
    default_without_external_files,
    rest,
    tmp_path,
    capsys,
):
    spec = SPECS[key]
    payload = inputs(spec)
    opts = dict(include_snapshot_text=False, response_char_limit=0)
    http = rest.post(spec.rest_path, json=payload, params={**opts, "as_of": AS_OF})
    mcp = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "false", "--response-char-limit", "0"],
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error
    assert code == 0
    values = [http.json(), mcp.structured_content, cli]
    expected = business(values[0])
    assert expected == business(values[1]) == business(values[2])
    assert de440_solar.MODEL_ID in json.dumps(expected, ensure_ascii=False)
    assert '"jpl_de440"' in json.dumps(expected, ensure_ascii=False)
    assert '"accuracy_certified": true' not in json.dumps(expected)
