"""Independent NOAA fixtures, north-reference fidelity and real protocol parity."""

import asyncio
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator, FormatChecker
from mpmath import mp
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.geomagnetic import field_zone, geomagnetic_reference
from fatebridge.core.fengshui.geomagnetic_inputs import GeomagneticReference
from fatebridge.core.fengshui.models import DirectionsRequest, XuankongRequest
from fatebridge.core.schema_cache import model_schema
from fatebridge.mcp_server import app
from fatebridge.services.fengshui import calculate_directions
from tests.support.fengshui_transports import mcp_call
from tests.support.mcp_result_assertions import (
    same_run_projected_response,
    without_transport,
)
from tests.support.transports import call_calculation, rest_client
from validation.geomagnetic import audit_noaa_c_vectors, audit_noaa_vectors

FOLDER = Path(__file__).parents[1] / "data/fengshui_geomagnetic_v1"
DATA = (
    Path(__file__).parents[2]
    / "src/fatebridge/data/fengshui/geomagnetic-wmm2025-v1.json"
)


def inputs(**patch):
    return {
        "latitude": 80,
        "longitude": 0,
        "height_km_wgs84": 0,
        "decimal_year": 2025.0,
        "evidence": "NOAA官方计算例；非实际房屋方向",
        **patch,
    }


def calculate(**patch):
    return geomagnetic_reference(GeomagneticReference.model_validate(inputs(**patch)))


def test_all_independent_official_vectors_remain_auditable_at_their_literal_precision() -> (
    None
):
    small = audit_noaa_vectors(
        (FOLDER / "NOAA_12_test_values.txt").read_text(), layout="published_12"
    )
    large = audit_noaa_vectors(
        (FOLDER / "NOAA_100_test_values.txt").read_text(), layout="coefficient_zip_100"
    )
    assert small["rows"] == 12 and small["matched_at_published_precision"] == 84
    assert small["all_published_precision_checks_passed"]
    assert large["rows"] == 100 and large["comparisons"] == 700
    # Keep the genuine sub-milli-nT published-source discrepancy visible. Tests do
    # not relabel it as a six-decimal pass or drop hard reference rows.
    assert not large["all_published_precision_checks_passed"]
    assert large["disagreements"] and large["maximum_absolute_difference"]["x"] > 0.0005
    assert all(r["component"] not in ("d", "i") for r in large["disagreements"])


def test_original_noaa_c_constant_discrepancies_and_reference_corruption_guards() -> (
    None
):
    reference = json.loads((FOLDER / "NOAA_C_100_main_field_values.json").read_text())
    raw = (FOLDER / "NOAA_100_test_values.txt").read_text()
    audit = audit_noaa_c_vectors(reference, raw)
    assert audit["rows"] == 100 and audit["comparisons"] == 700
    # Original unmodified C uses a rounded semiminor axis. Retain this separate
    # 100-row gate and its discrepancies after the exact-WGS84 repair.
    assert not audit["official_c_implementation_agreement"]
    assert len(audit["disagreements"]) == 340
    changed = deepcopy(reference)
    changed["vectors"][0]["field"]["x"] += 1
    corrupt = audit_noaa_c_vectors(changed, raw)
    assert any(
        row["row"] == 1
        and row["component"] == "x"
        and row["absolute_difference"] > 0.99
        for row in corrupt["disagreements"]
    )
    changed["vectors"].pop()
    with pytest.raises(ValueError):
        audit_noaa_c_vectors(changed, raw)


@pytest.mark.parametrize(
    "source_row,field",
    [
        (23, "north_component_nt"),
        (24, "east_component_nt"),
        (25, "down_component_nt"),
        (29, "total_intensity_nt"),
        (30, "horizontal_intensity_nt"),
        (31, "declination_degrees_east"),
        (32, "inclination_degrees_down"),
    ],
)
def test_primary_report_table3b_main_fields_at_their_printed_precision(
    source_row: int, field: str
) -> None:
    reference = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/fengshui-wmm2025-report-table3b.json"
        ).read_text()
    )
    source = reference["table3a_input"]
    result = calculate(
        latitude=float(source["latitude"]),
        longitude=float(source["longitude_public_equivalent"]),
        height_km_wgs84=float(source["height_km_wgs84"]),
        decimal_year=float(source["decimal_year"]),
    )["field"][field]
    printed = reference["rows"][source_row - 1]
    assert printed["row"] == source_row
    if printed["unit"] == "rad":
        result = math.radians(result)
    else:
        pass
    expected = Decimal(printed["value"])
    half_last_place = Decimal(1).scaleb(expected.as_tuple().exponent) / 2
    assert abs(Decimal.from_float(result) - expected) <= half_last_place


def test_all_frozen_wgs84_cohorts_match_independent_rodrigues_binary64_rounding() -> (
    None
):
    reference = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/fengshui-wmm-wgs84-reference-v1.json"
        ).read_text()
    )
    assert reference["reference_precisions"] == [80, 120]
    assert reference["coefficient_sha256"] == (
        "dfa8597825af4e0b87ff4198a5b4fb661b3c49f4cd090cd0164e0259b075582f"
    )
    assert [len(c["inputs"]) for c in reference["cohorts"]] == [100, 12, 2388, 64]
    fields = (
        "north_component_nt",
        "east_component_nt",
        "down_component_nt",
        "horizontal_intensity_nt",
        "total_intensity_nt",
        "inclination_degrees_down",
        "declination_degrees_east",
    )
    for cohort in reference["cohorts"]:
        assert len(cohort["inputs"]) == len(cohort["expected"])
        for raw, expected in zip(cohort["inputs"], cohort["expected"]):
            year, height, latitude, longitude = map(float, raw)
            result = calculate(
                latitude=latitude,
                longitude=(longitude + 180) % 360 - 180,
                height_km_wgs84=height,
                decimal_year=year,
            )
            assert result["field"] == dict(zip(fields, map(float, expected))), (
                cohort["cohort"],
                raw,
            )


def test_field_arithmetic_does_not_depend_on_process_global_precision() -> None:
    expected = calculate()["field"]
    with mp.workdps(7):
        assert calculate()["field"] == expected
    with mp.workdps(90):
        assert calculate()["field"] == expected


def test_missing_components_and_nonfinite_references_cannot_pass_numeric_acceptance() -> (
    None
):
    reference = json.loads((FOLDER / "NOAA_C_100_main_field_values.json").read_text())
    raw = (FOLDER / "NOAA_100_test_values.txt").read_text()
    for value in (float("nan"), float("inf"), True):
        changed = deepcopy(reference)
        changed["vectors"][0]["field"]["x"] = value
        with pytest.raises(ValueError):
            audit_noaa_c_vectors(changed, raw)
    raw12 = (FOLDER / "NOAA_12_test_values.txt").read_text()
    rows = [
        row.split() for row in raw12.splitlines() if row and not row.startswith("#")
    ]
    rows[0] = rows[0][:10]
    with pytest.raises(ValueError):
        audit_noaa_vectors(
            "\n".join(" ".join(row) for row in rows), layout="published_12"
        )


def test_oracle_integrity_all_degree_twelve_coefficients_and_no_mutation() -> None:
    manifest = json.loads((FOLDER / "provenance.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest
    bundle = json.loads(DATA.read_text())
    rows = []
    for line in (FOLDER / "WMM2025.COF").read_text().splitlines()[1:]:
        if line.startswith("9999"):
            break
        else:
            pass
        parts = line.split()
        rows.append([int(parts[0]), int(parts[1]), *map(float, parts[2:])])
    assert bundle["coefficients"] == rows
    assert {(r[0], r[1]) for r in rows} == {
        (n, m) for n in range(1, 13) for m in range(n + 1)
    }
    first = calculate()
    first["ruleset"]["source_ids"].append("caller mutation")
    assert "caller mutation" not in calculate()["ruleset"]["source_ids"]


def test_oracle_audit_rejects_removed_or_duplicated_reference_rows_and_detects_corruption() -> (
    None
):
    raw = (FOLDER / "NOAA_12_test_values.txt").read_text()
    rows = [s for s in raw.splitlines() if s and not s.startswith("#")]
    for changed in (rows[:-1], [rows[0]] * 12):
        with pytest.raises(ValueError):
            audit_noaa_vectors("\n".join(changed), layout="published_12")
    parts = rows[0].split()
    parts[4] = "7521.6"
    rows[0] = " ".join(parts)
    audit = audit_noaa_vectors("\n".join(rows), layout="published_12")
    assert not audit["all_published_precision_checks_passed"]
    assert audit["disagreements"][0]["component"] == "x"


@pytest.mark.parametrize(
    "north,longitude", [("true", 0), ("magnetic", 0), ("true", 120), ("magnetic", 120)]
)
@pytest.mark.parametrize("bearing", [0, 360, 7.5, 359.9])
def test_signed_conversion_wraps_keeps_raw_bearing_and_never_confirms_a_house(
    north: str, longitude: int, bearing: float | int
) -> None:
    kwargs = {"bearing_degrees": bearing, "north_reference": north}
    original = calculate_directions(**kwargs)["layers"]["directions"]
    result = calculate_directions(
        **kwargs,
        geomagnetic_reference=inputs(
            latitude=0 if longitude == 120 else 80, longitude=longitude
        ),
    )
    layer = result["layers"]["directions"]
    assert layer["bearing"] == original["bearing"]
    assert layer["directions"] == original["directions"]
    geomag = layer["geomagnetic_reference"]
    conversion = geomag["conversion"]
    candidate = conversion["candidate"]
    declination = geomag["field"]["declination_degrees_east"]
    expected = (bearing + (declination if north == "magnetic" else -declination)) % 360
    assert candidate["bearing_degrees"] == pytest.approx(expected, abs=1e-12)
    assert candidate["north_reference"] != north
    assert conversion["status"] == "model_candidate"
    assert (
        conversion["original_input_retained"]
        and not conversion["automatically_applied_to_house"]
    )
    assert not geomag["heading_context"]["site_measurement_confirmed"]
    assert not geomag["uncertainty"]["converted_to_bearing_uncertainty_interval"]
    assert result["rulesets"][-1]["ruleset_id"] == "geomagnetic_wmm2025_v1"
    assert "尚未确认现场方向" in result["snapshot_text"]


@pytest.mark.parametrize(
    "north,bearing,direction,trigram,mountain,numerator",
    [
        ("magnetic", 21.218517883865147, "N", "坎", "癸", "25332747903959039"),
        ("true", 158.78148211613484, "SE", "巽", "巳", "177329235327713265"),
    ],
)
def test_heading_conversion_partitions_before_display_rounding(
    north: str,
    bearing: float,
    direction: str,
    trigram: str,
    mountain: str,
    numerator: str,
) -> None:
    # The original independent Rodrigues/NOAA80N,0E reference fixes delivered D.
    # These supplied binary64 headings put the exact sum just below a cell edge.
    original = calculate_directions(bearing_degrees=bearing, north_reference=north)
    result = calculate_directions(
        bearing_degrees=bearing,
        north_reference=north,
        geomagnetic_reference=inputs(),
    )
    layer = result["layers"]["directions"]
    geomagnetic = layer["geomagnetic_reference"]
    conversion = geomagnetic["conversion"]
    candidate = conversion["candidate"]
    assert geomagnetic["field"]["declination_degrees_east"].hex() == (
        "0x1.480f36433543cp+0"
    )
    assert layer["bearing"] == original["layers"]["directions"]["bearing"]
    assert (candidate["direction"], candidate["trigram"], candidate["mountain"]) == (
        direction,
        trigram,
        mountain,
    )
    assert candidate["bearing_degrees"] == (22.5 if north == "magnetic" else 157.5)
    assert conversion["angle_exact"] == {
        "numerator": numerator,
        "denominator": "1125899906842624",
    }
    assert not conversion["automatically_applied_to_house"]


def test_heading_conversion_keeps_wrapped_display_zero() -> None:
    result = calculate_directions(
        bearing_degrees=1.2814821161348522,
        north_reference="true",
        geomagnetic_reference=inputs(),
    )
    conversion = result["layers"]["directions"]["geomagnetic_reference"]["conversion"]
    candidate = conversion["candidate"]
    assert candidate["bearing_degrees"] == 0.0
    assert (candidate["direction"], candidate["mountain"]) == ("N", "子")
    assert conversion["angle_exact"] == {
        "numerator": "1621295865853378559",
        "denominator": "4503599627370496",
    }


@pytest.mark.parametrize("height", [-1, 0, 100, 850])
def test_explicit_altitude_full_numeric_field_and_no_bearing_invention(height) -> None:
    r = calculate(height_km_wgs84=height)
    f = r["field"]
    assert f["horizontal_intensity_nt"] ** 2 == pytest.approx(
        f["north_component_nt"] ** 2 + f["east_component_nt"] ** 2
    )
    assert f["total_intensity_nt"] ** 2 == pytest.approx(
        f["horizontal_intensity_nt"] ** 2 + f["down_component_nt"] ** 2
    )
    assert r["conversion"]["status"] == "not_requested"
    assert r["conversion"]["candidate"] is None
    assert r["uncertainty"]["declination_degrees"] == pytest.approx(
        (0.26**2 + (5417 / f["horizontal_intensity_nt"]) ** 2) ** 0.5
    )
    assert "earth_surface_not_hard_bound" in r["uncertainty"]["interpretation"]


@pytest.mark.parametrize(
    "latitude,longitude,height,reason",
    [
        (90, 0, 0, "geographic_pole"),
        (-90, 0, 0, "geographic_pole"),
        (89, -121, 28, "magnetic_blackout"),
    ],
)
def test_unusable_heading_keeps_fields_but_blocks_candidate(
    latitude, longitude, height: int, reason: str
) -> None:
    req = GeomagneticReference.model_validate(
        inputs(latitude=latitude, longitude=longitude, height_km_wgs84=height)
    )
    r = geomagnetic_reference(req, 180, "true")
    assert r["calculation_status"] == "complete"
    assert r["conversion"]["status"] == "unavailable"
    assert r["conversion"]["unavailable_reason"] == reason
    assert r["conversion"]["candidate"] is None
    assert not r["heading_context"]["declination_usable_as_heading_reference"]


def test_caution_thresholds_and_unconfirmed_time_space_weather() -> None:
    assert [field_zone(h) for h in (1999.99, 2000, 5999.99, 6000)] == [
        "blackout",
        "caution",
        "caution",
        "normal",
    ]
    r = calculate(latitude=80, longitude=-96, height_km_wgs84=48)
    assert r["heading_context"]["zone"] == "caution"
    assert not r["heading_context"]["space_weather_checked"]


def test_leap_year_decimal_reference_uses_actual_days_and_date_has_no_implicit_local_zone() -> (
    None
):
    data = inputs()
    data.pop("decimal_year")
    req = GeomagneticReference.model_validate({**data, "model_date": "2028-07-02"})
    assert req.year_value() == 2028.5
    assert req.model_date == date(2028, 7, 2)
    req2 = GeomagneticReference.model_validate({**data, "model_date": "2029-12-31"})
    assert req2.year_value() == 2029 + 364 / 365
    r = geomagnetic_reference(req)
    assert r["input"]["date_convention"] == "UTC_start_of_reference_date"


@pytest.mark.parametrize(
    "patch,remove",
    [
        ({}, "height_km_wgs84"),
        ({}, "evidence"),
        ({}, "decimal_year"),
        ({"model_date": "2026-01-01"}, None),
        ({"model_date": "2030-01-01", "decimal_year": None}, None),
        ({"model_date": "2024-12-31", "decimal_year": None}, None),
        ({"model_date": "2026-01-01T00:00:00Z", "decimal_year": None}, None),
        ({"decimal_year": 2030}, None),
        ({"decimal_year": 2024.99}, None),
        ({"height_km_wgs84": 851}, None),
        ({"height_km_wgs84": -1.01}, None),
        ({"latitude": 90.1}, None),
        ({"longitude": 181}, None),
        ({"evidence": "  "}, None),
        ({"latitude": True}, None),
        ({"decimal_year": "2026"}, None),
        ({"model_id": "wmm2020_v1"}, None),
    ],
)
def test_rejects_ambiguous_or_unsupported_inputs_in_runtime_and_schema(
    patch, remove: str | None
) -> None:
    data = inputs(**patch)
    if remove:
        data.pop(remove)
    else:
        pass
    with pytest.raises(ValidationError):
        GeomagneticReference.model_validate(data)
    schema = model_schema(GeomagneticReference)
    assert list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data)
    )


def test_request_local_model_instances_are_deterministic_under_parallel_load() -> None:
    data = [
        inputs(latitude=lat, longitude=lon, decimal_year=year)
        for lat, lon, year in [(80, 0, 2025), (0, 120, 2027.5), (-80, -120, 2029.9)]
    ] * 6

    def field(d):
        return geomagnetic_reference(GeomagneticReference.model_validate(d))["field"]

    serial = list(map(field, data))
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(field, data)) == serial


def test_historical_natal_still_rejects_unconfirmed_true_bearing() -> None:
    with pytest.raises(ValidationError):
        XuankongRequest.model_validate(
            {"house": {"facing_degrees": 180, "north_reference": "true"}}
        )
    with pytest.raises(ValidationError):
        DirectionsRequest.model_validate(
            {"bearing_degrees": 180, "geomagnetic_reference": inputs()}
        )


def test_optional_reference_matches_rest_real_mcp_and_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = {
        "bearing_degrees": 180,
        "north_reference": "true",
        "geomagnetic_reference": inputs(),
    }
    http = rest_client(monkeypatch).post("/api/fengshui/directions", json=data)
    protocol = asyncio.run(mcp_call("directions", data))
    path = tmp_path / "magnetic.json"
    path.write_text(json.dumps(data))
    assert run(["fengshui_directions", "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )


def test_real_mcp_projection_keeps_all_conversion_conditions_and_model_provenance() -> (
    None
):
    result = asyncio.run(
        mcp_call(
            "directions",
            {
                "bearing_degrees": 0,
                "north_reference": "true",
                "geomagnetic_reference": inputs(),
                "fields": [
                    "layers.directions.bearing",
                    "layers.directions.geomagnetic_reference",
                    "rulesets",
                    "source_catalog",
                    "rule_trace",
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    assert not result.is_error
    d = result.structured_content["layers"]["directions"]
    assert d["bearing"]["north_reference"] == "true"
    assert (
        d["geomagnetic_reference"]["conversion"]["candidate"]["north_reference"]
        == "magnetic"
    )
    assert (
        result.structured_content["rule_trace"][-1]["method"]
        == "geophysical_heading_reference"
    )
    assert "GM1" in result.structured_content["source_catalog"]


def test_strict_evidence_business_projection_fits_real_default_mcp_budget() -> None:
    async def invoke():
        async with Client(app) as client:
            result = await call_calculation(
                client,
                "fengshui_directions",
                {
                    "bearing_degrees": 0,
                    "north_reference": "true",
                    "geomagnetic_reference": inputs(),
                    "fields": [
                        "layers.directions.bearing",
                        "layers.directions.geomagnetic_reference",
                        "rulesets",
                        "source_catalog",
                        "rule_trace",
                    ],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            return await same_run_projected_response(client, result)

    body = asyncio.run(invoke())
    assert (
        body["layers"]["directions"]["geomagnetic_reference"]["conversion"][
            "candidate"
        ]["north_reference"]
        == "magnetic"
    )
    assert set(body["rulesets"][-1]["source_ids"]) == {
        "GM1",
        "GM2",
        "GM3",
        "GM5",
        "GM6",
        "GM7",
    }
    assert set(body["rulesets"][-1]["source_ids"]) <= body["source_catalog"].keys()
