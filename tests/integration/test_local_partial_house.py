"""A missing reference house layer must preserve the other computed layers."""

import copy
import gzip
import hashlib
from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.local_techniques import chart as local_chart
from tests.support.transports import SPECS, business, rest, surface_calls


class Control(TypedDict):
    id: str
    payload: dict[str, JsonValue]


class Point(TypedDict):
    id: str
    lon: float
    sign: str
    signlon: float


class Reference(TypedDict):
    metadata: dict[str, JsonValue]
    core: dict[str, JsonValue]
    planets: list[Point]
    source_rulesets: list[dict[str, JsonValue]]
    source_validation: dict[str, JsonValue]
    controls: list[Control]


@pytest.fixture(scope="module")
def partial_source() -> Reference:
    folder = Path(__file__).parents[1] / "data/local_partial_house_v1"
    raw = gzip.decompress((folder / "source.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (folder / "source.json.sha256").read_text().strip()
        == "ed091aca2b013286e3aa5f645fd9ae20bd0cbfef643432842eed27be130e7cc9"
    )
    reference = TypeAdapter(Reference).validate_json(raw)
    assert reference["metadata"]["source_is_independent_numeric_oracle"] is False
    assert reference["metadata"]["criteria_sha256"] == (
        "68c71f46b08ad65489552360c92f91dd5dfaad66c8fe859e7c0816eb49aa3af1"
    )
    assert len(reference["controls"]) == 24
    return reference


def _assert_partial_house_value(
    value: dict, control: dict[str, JsonValue], partial_source: Reference
) -> None:
    chart = value["chart"]
    assert chart["ok"] is True
    assert chart["houses"] == []
    assert chart["angles"] == {"ascendant": None, "midheaven": None}
    assert [
        {k: point[k] for k in ("id", "lon", "sign", "signlon")}
        for point in chart["objects"]
    ] == partial_source["planets"]
    assert all(point["house"] is None for point in chart["objects"])
    assert value["params"]["houseStartModeApplied"] is None
    assert value["params"]["houseOrientation"] is None
    assert value["params"]["houseGeometryStatus"] == "unavailable_selected_reference"
    assert value["validation"]["chart_source"] == partial_source["source_validation"]
    assert value["validation"]["chart_source"]["classical_acceptance_passed"] is False
    assert value["rulesets"]["chart"] == partial_source["source_rulesets"]
    assert "calendar" in value["rulesets"]
    assert value["sukuyo"]["day_mansion"]
    assert value["sukuyo"]["calendar"]["birth_time_known"] is True
    layers = value["validation"]["calculation_layers"]
    assert layers["calendar"] == value["sukuyo"]["calendar"]["status"]
    assert layers["chart"] == layers["planet_positions"] == "computed"
    assert layers["house_geometry"] == "unavailable_selected_reference"
    if control["payload"]["doubing_su28"]:
        assert value["astronomy"] is not None
        assert "Sun" in {p["id"] for p in value["astronomy"]["bodies"]}
        assert layers["astronomy"] == "computed"
    else:
        assert value["astronomy"] is None
        assert all("su28" not in point for point in chart["objects"])
        assert layers["astronomy"] == "not_computed"
    snapshot = value["snapshot_text"]
    assert "参考宫位未定" in snapshot and "HouseNone" not in snapshot
    assert "星图来源与适用范围" in snapshot
    assert all(f"星曜：{p['id']} " in snapshot for p in partial_source["planets"])


def test_canonical_partial_geometry_survives_each_local_option(
    partial_source: Reference, monkeypatch: pytest.MonkeyPatch, rest
) -> None:
    def source(*args: object, **kwargs: object) -> dict[str, JsonValue]:
        return copy.deepcopy(partial_source["core"])

    monkeypatch.setattr(local_chart, "build_core_chart_payload", source)
    params = {
        "as_of": "2026-11-12T00:00:00Z",
        "response_char_limit": 0,
        "include_snapshot_text": "true",
    }
    for control in partial_source["controls"]:
        response = rest.post(
            SPECS["suzhan"].rest_path,
            json={
                name: value
                for name, value in control["payload"].items()
                if name != "mansion_method"
            },
            params=params,
        )
        assert response.status_code == 200, response.text
        _assert_partial_house_value(response.json(), control, partial_source)


def test_canonical_partial_geometry_representative_options_agree_across_transports(
    partial_source: Reference, monkeypatch: pytest.MonkeyPatch, surface_calls
) -> None:
    def source(*args: object, **kwargs: object) -> dict[str, JsonValue]:
        return copy.deepcopy(partial_source["core"])

    monkeypatch.setattr(local_chart, "build_core_chart_payload", source)
    representatives = [
        next(
            control
            for control in partial_source["controls"]
            if control["payload"]["doubing_su28"] is include_mansions
        )
        for include_mansions in (False, True)
    ]
    for control in representatives:
        response, protocol, code, cli = surface_calls(
            SPECS["suzhan"],
            {
                name: value
                for name, value in control["payload"].items()
                if name != "mansion_method"
            },
            projection=dict(
                as_of="2026-11-12T00:00:00Z",
                response_char_limit=0,
                include_snapshot_text=True,
            ),
        )
        assert response.status_code == 200, response.text
        assert code == 0 and not protocol.is_error
        values = [response.json(), cli, protocol.structured_content]
        assert business(values[0]) == business(values[1]) == business(values[2])
        for value in values:
            _assert_partial_house_value(value, control, partial_source)
