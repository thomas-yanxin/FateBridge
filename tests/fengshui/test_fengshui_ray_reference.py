"""Exact CGAL finite-ray controls, preserving original numerical failures."""

import gzip
import hashlib
import math
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError
from shapely.geometry import Polygon
from typing_extensions import TypedDict

from fatebridge.core.fengshui import spatial_geometry as geometry
from fatebridge.core.fengshui.spatial_inputs import (
    PlanPoint,
    PlanRectangle,
    PlanSegment,
)
from tests.support.transports import SPECS, business, rest, surface_calls


class RayRow(TypedDict):
    origin: list[float]
    vector: list[float]
    target: list[list[float]]
    reach: float
    group: str
    nearest_parameter: str | None


class CornerRow(TypedDict):
    center: list[float]
    width: float
    depth: float
    angle: float
    sine: float
    cosine: float
    target: list[list[float]]
    reach: float
    group: str
    expected: bool
    expected_mask: int


class BackingRow(TypedDict):
    origin: list[float]
    facing: float
    vector: list[float]
    segments: list[list[list[float]]]
    reach: float
    group: str
    nearest_parameter: str | None
    distance_squared: str | None
    expected_distance: float | None


class PublicControl(TypedDict):
    id: str
    key: str
    payload: dict[str, object]


class Reference(TypedDict):
    metadata: dict[str, object]
    rays: list[RayRow]
    corners: list[CornerRow]
    backing: list[BackingRow]
    public_controls: list[PublicControl]


@pytest.fixture(scope="module")
def reference() -> Reference:
    folder = Path(__file__).parents[1] / "data/fengshui_rays_cgal_v1"
    raw = gzip.decompress((folder / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (folder / "reference.json.sha256").read_text().strip()
    )
    result = TypeAdapter(Reference).validate_json(raw)
    assert result["metadata"]["fatebridge_imported"] is False
    assert result["metadata"]["cgal_version"] == "6.2.1"
    assert result["metadata"]["criteria_sha256"] == (
        "6b60c9286bcead07263344bfd08dcea176bad23a6e604e6ec1efb9726207e672"
    )
    return result


def test_closed_convex_finite_ray_parameters_match_actual_cgal(reference: Reference):
    assert len(reference["rays"]) == 17056
    for i, row in enumerate(reference["rays"]):
        actual = geometry._ray_parameter(
            (Fraction(row["origin"][0]), Fraction(row["origin"][1])),
            (Fraction(row["vector"][0]), Fraction(row["vector"][1])),
            [(Fraction(x), Fraction(y)) for x, y in row["target"]],
            Fraction(row["reach"]) ** 2,
        )
        expected = row["nearest_parameter"]
        assert actual == (None if expected is None else Fraction(expected)), (i, row)


def test_corner_presence_and_four_ray_masks_match_actual_cgal(reference: Reference):
    assert len(reference["corners"]) == 6296
    for i, row in enumerate(reference["corners"]):
        rectangle = PlanRectangle(
            center=PlanPoint(x=row["center"][0], y=row["center"][1]),
            width_m=row["width"],
            depth_m=row["depth"],
            rotation_degrees=row["angle"],
        )
        assert (
            geometry.corner_points_at(rectangle, Polygon(row["target"]), row["reach"])
            is row["expected"]
        ), (i, row)
        # The reference supplies the rational matrix independently. Check every
        # finite ray as well as the composite public corner boolean above.
        cx, cy = Fraction(row["center"][0]), Fraction(row["center"][1])
        sine, cosine = Fraction(row["sine"]), Fraction(row["cosine"])
        vertices = [(Fraction(x), Fraction(y)) for x, y in row["target"]]
        mask = 0
        for index, (sx, sy) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
            x, y = sx * Fraction(row["width"]) / 2, sy * Fraction(row["depth"]) / 2
            vx, vy = x * cosine + y * sine, -x * sine + y * cosine
            if (
                geometry._ray_parameter(
                    (cx + vx, cy + vy), (vx, vy), vertices, Fraction(row["reach"]) ** 2
                )
                is not None
            ):
                mask |= 1 << index
        assert mask == row["expected_mask"], (i, row, mask)


def test_valid_backing_segments_match_actual_cgal_presence_and_distance(
    reference: Reference,
):
    qualified = 0
    for i, row in enumerate(reference["backing"]):
        if row["group"] == "raw_collapsed_segment_model_control":
            continue
        qualified += 1
        segments = [
            PlanSegment(start=PlanPoint(x=a[0], y=a[1]), end=PlanPoint(x=b[0], y=b[1]))
            for a, b in row["segments"]
        ]
        actual = geometry.rear_backing_distance(
            PlanPoint(x=row["origin"][0], y=row["origin"][1]),
            row["facing"],
            segments,
            row["reach"],
        )
        expected = row["expected_distance"]
        if expected is None:
            assert actual is None, (i, row, actual)
        else:
            tolerance = (
                2 * math.ulp(expected)
                if expected != 0 and (abs(expected) < 1e-100 or abs(expected) > 1e100)
                else 2e-12
            )
            assert actual is not None and math.isfinite(actual), (i, row, actual)
            assert abs(actual - expected) <= tolerance, (i, row, actual)
    assert (len(reference["backing"]), qualified) == (9478, 9454)


def test_collapsed_internal_controls_do_not_expand_public_segment_schema(
    reference: Reference,
):
    controls = [
        row
        for row in reference["backing"]
        if row["group"] == "raw_collapsed_segment_model_control"
    ]
    assert len(controls) == 24
    for row in controls:
        ((a, b),) = row["segments"]
        with pytest.raises(ValidationError, match="线段两端不能重合"):
            PlanSegment(start=PlanPoint(x=a[0], y=a[1]), end=PlanPoint(x=b[0], y=b[1]))
        actual = geometry._ray_parameter(
            (Fraction(row["origin"][0]), Fraction(row["origin"][1])),
            (Fraction(row["vector"][0]), Fraction(row["vector"][1])),
            [(Fraction(x), Fraction(y)) for x, y in (a, b)],
            Fraction(row["reach"]) ** 2,
        )
        expected = row["nearest_parameter"]
        assert actual == (None if expected is None else Fraction(expected)), row


@pytest.mark.parametrize("control_index", range(18))
def test_exact_contacts_preserve_shape_facts_and_public_search_qualification(
    reference: Reference, control_index: int, surface_calls
):
    control = reference["public_controls"][control_index]
    fields = ["layout_analysis.workstation_layout_analysis"]
    options = dict(
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
        include_snapshot_text=False,
        as_of="2026-11-11T03:00:00Z",
    )
    response, protocol, code, cli = surface_calls(
        SPECS["fengshui_assess"], control["payload"], projection=options
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    actual = business(response.json())
    assert actual == business(cli) == business(protocol.structured_content)
    branch = actual["layout_analysis"]["workstation_layout_analysis"]
    assert branch["geometry"]["physically_feasible"] is True
    seat = branch["geometry"]["seats"][0]
    receipt = branch["search"]["receipts"][0]
    if control["id"].startswith("backing-"):
        assert seat["form"]["solid_backing"] is True
        assert abs(seat["backing_distance_m"] - math.sqrt(2)) <= 2e-12
        assert receipt["status"] == "ready"
        assert branch["search"]["returned_candidate_ids"] == ["spatial-0001"]
    elif control["id"] == "corner-shape-known-rounded":
        assert seat["form"]["sharp_corner_points_at_user"] is False
        assert receipt["status"] == "ready"
    elif control["id"] == "corner-shape-unknown":
        assert seat["form"]["sharp_corner_points_at_user"] is None
        assert receipt["status"] == "conditional_option"
        assert receipt["pending_confirmations"] == [
            "workstation_layout.scene.desk.no_sharp_corner"
        ]
    else:
        assert seat["form"]["sharp_corner_points_at_user"] is True
        assert receipt["status"] == "blocked"
        assert receipt["blocking_reasons"] == ["required_check:desk:no_sharp_corner"]
        assert branch["search"]["returned_candidate_ids"] == []
