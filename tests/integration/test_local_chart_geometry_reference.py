"""Frozen source inputs and independently executed CGAL circle predicates.

The source injection isolates these exact predicates from different native
astronomy builds. Live physical-source/protocol runs have separate evidence.
"""

import copy
import gzip
import hashlib
from fractions import Fraction
from pathlib import Path

import pytest
from mpmath import mp
from pydantic import TypeAdapter
from typing_extensions import NotRequired, TypedDict

from fatebridge.core.astro import house_projection_precision, runtime
from fatebridge.core.astro.geometry import _sign_name
from fatebridge.core.astro.house_positions import EclipticHouseProjection
from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.local_techniques import chart as local_chart
from fatebridge.core.local_techniques.chart import ZODIAC_SIGN_CN
from fatebridge.core.local_techniques.house_geometry import HouseGeometry
from tests.support.transports import SPECS, business, rest, surface_calls


class Ring(TypedDict):
    anchor: float
    reverse: bool
    cusps: list[str]
    expected_float: list[float]
    expected_signs: list[int]


class Sign(TypedDict):
    point: str
    expected_sign: int


class Circle(TypedDict):
    group: str
    anchor: float | None
    reverse: bool
    cusps: list[str]
    point: str
    declared_partition: bool
    expected_house: int | None


class Point(TypedDict):
    id: str
    lon: float
    sign: str
    signlon: float
    house: str
    native_phase_ratio: NotRequired[str]


class House(TypedDict):
    id: str
    lon: float
    sign: str


class PublicControl(TypedDict):
    id: str
    key: str
    payload: dict[str, object]
    expect_final_error: bool
    reference_kind: str
    expected_points: list[Point]
    expected_houses: NotRequired[list[House]]
    expected_source_system: NotRequired[str]
    source_core: NotRequired[dict[str, object]]


class PhaseControl(TypedDict):
    base: int
    sign: int
    exponent: int
    expected_houses: list[int]


class Reference(TypedDict):
    metadata: dict[str, object]
    rings: list[Ring]
    phases: list[Sign]
    houses: list[Circle]
    public_controls: list[PublicControl]
    working_phase_controls: list[PhaseControl]


@pytest.fixture(scope="module")
def reference() -> Reference:
    folder = Path(__file__).parents[1] / "data/local_house_geometry_cgal_v1"
    raw = gzip.decompress((folder / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (folder / "reference.json.sha256").read_text().strip()
        == "4adc9c61ebedf5041a13941c1ddfec44f70a7163e4fe443c927e002fd75a1edb"
    )
    result = TypeAdapter(Reference).validate_json(raw)
    assert result["metadata"]["fatebridge_imported"] is False
    assert result["metadata"]["cgal_version"] == "6.2.1"
    assert result["metadata"]["criteria_sha256"] == (
        "975e172254f85ebca55fd2266eefc1782546339417c57b3b14138e2728f02e8c"
    )
    assert result["metadata"]["original_scalar_checks"] == 35447
    return result


def test_original_exact_rings_and_sign_partitions(reference: Reference):
    assert len(reference["rings"]) == 240 and len(reference["phases"]) == 159
    for i, row in enumerate(reference["rings"]):
        geometry = HouseGeometry.equal(row["anchor"], reverse=row["reverse"])
        assert geometry.cusps == tuple(map(Fraction, row["cusps"])), (i, row)
        records = geometry.records(ZODIAC_SIGN_CN)
        assert [r["lon"] for r in records] == row["expected_float"], (i, row)
        assert [r["sign"] for r in records] == [
            SIGNS[k] for k in row["expected_signs"]
        ], (i, row)
        assert all(0 <= r["lon"] < 360 for r in records)
    for i, row in enumerate(reference["phases"]):
        assert (
            _sign_name(float(Fraction(row["point"]))) == SIGNS[row["expected_sign"]]
        ), (i, row)


def test_all_original_circle_decisions_and_nonpartition_qualifications(
    reference: Reference,
):
    assert len(reference["houses"]) == 31784
    qualified = nonpartition = 0
    for i, row in enumerate(reference["houses"]):
        if not row["declared_partition"]:
            nonpartition += 1
            assert row["expected_house"] is None
            with pytest.raises(ValueError, match="Nonpartition"):
                HouseGeometry(tuple(map(Fraction, row["cusps"])), row["reverse"])
            continue
        qualified += 1
        geometry = HouseGeometry(tuple(map(Fraction, row["cusps"])), row["reverse"])
        assert geometry.house(Fraction(row["point"])) == row["expected_house"], (
            i,
            row,
        )
    assert (qualified, nonpartition) == (29528, 2256)


@pytest.mark.parametrize("control_index", range(36))
def test_working_projection_phase_survives_its_display_precision(
    reference: Reference, control_index: int, monkeypatch
):
    """Constructed phase controls; these do not certify a physical projection."""
    row = reference["working_phase_controls"][control_index]

    def phase_model(latitude, armc, obliquity, longitude, code, digits):
        context = mp.clone()
        context.dps = digits
        target = (
            context.mpf(row["base"]) + row["sign"] * context.mpf(2) ** -row["exponent"]
        ) % 360
        return context, (target - context.mpf(1) / 3600000) % 360

    monkeypatch.setattr(house_projection_precision, "_phase", phase_model)
    monkeypatch.setattr(runtime, "ephemeris_call", lambda *args, **kwargs: 0.0)
    projection = EclipticHouseProjection(10.0, 20.0, 23.4, b"C")
    coordinate = projection.coordinate(50.0)
    assert isinstance(coordinate.phase_degrees, Fraction)
    assert int(coordinate.position) == row["expected_houses"][0]
    for reverse in (False, True):
        geometry = HouseGeometry(
            tuple(Fraction((-30 if reverse else 30) * i) % 360 for i in range(12)),
            reverse=reverse,
            projected=True,
        )
        assert (
            geometry.house(50.0, projected_phase=coordinate.phase_degrees)
            == row["expected_houses"][int(reverse)]
        ), row


@pytest.mark.parametrize("control_index", range(62))
def test_frozen_source_geometry_reaches_qualified_public_models(
    reference: Reference, control_index: int, surface_calls, monkeypatch
):
    control = reference["public_controls"][control_index]
    if "source_core" in control:

        def frozen_source(*args: object, **kwargs: object) -> dict[str, object]:
            return copy.deepcopy(control["source_core"])

        monkeypatch.setattr(local_chart, "build_core_chart_payload", frozen_source)
    key = control["key"]
    fields = (
        ["chart", "params", "astronomy"]
        if key == "suzhan"
        else [
            "chart",
            "diceChart",
        ]
    )
    options = dict(
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
        include_snapshot_text=False,
        as_of="2026-11-12T00:00:00Z",
    )
    response, protocol, code, cli = surface_calls(
        SPECS[key], control["payload"], projection=options
    )
    if control["expect_final_error"]:
        assert response.status_code == 400 and code != 0 and protocol.is_error
        for value in (response.json(), cli, protocol.structured_content):
            assert value["error_code"] == "validation_error"
            assert value["retryable"] is False
        return
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    value = business(response.json())
    assert value == business(cli) == business(protocol.structured_content)
    if control["reference_kind"] == "date_only":
        assert value["chart"] is value["astronomy"] is None
        assert value["params"]["birthTimeKnown"] is False
        assert value["params"]["birthTimeImputed"] is False
        return
    if control["reference_kind"] == "symbolic_only":
        assert value["chart"] is None
        assert value["diceChart"]["params"]["engineBackend"] == "symbolic_rules"
        assert value["diceChart"]["chart"]["houses"][0]["lon"] == 180
        return
    chart = value["chart"] if key == "suzhan" else value["chart"]["chart"]
    params = value["params"] if key == "suzhan" else value["chart"]["params"]
    assert params["houseSystemResolved"] == control["expected_source_system"]
    assert [{k: row[k] for k in ("id", "lon", "sign")} for row in chart["houses"]] == (
        control["expected_houses"]
    )
    actual_points = {row["id"]: row for row in chart["objects"]}
    assert actual_points.keys() == {row["id"] for row in control["expected_points"]}
    for expected in control["expected_points"]:
        actual = actual_points[expected["id"]]
        for field in ("lon", "sign", "signlon", "house"):
            assert actual[field] == expected[field], (control["id"], expected, actual)
        assert 0 <= actual["lon"] < 360 and 0 <= actual["signlon"] < 30
        if "native_phase_ratio" in expected:
            assert actual["ecliptic_house_phase_degrees_ratio"] == (
                expected["native_phase_ratio"]
            )
    if control["payload"].get("gps_lat") in (-90, 90):
        assert (
            params["angleDefinition"]["fixed_direction_diurnal_rising_defined"] is False
        )
