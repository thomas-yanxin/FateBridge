"""Frozen independent CGAL/MP90/DEAP cases, including original failed controls."""

import gzip
import hashlib
import math
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from shapely.geometry import Polygon, box
from typing_extensions import TypedDict

from fatebridge.core.fengshui import spatial_angles as angles
from fatebridge.core.fengshui import spatial_geometry as geometry
from fatebridge.core.fengshui.spatial_domains import resolve_search_domains
from fatebridge.core.fengshui.spatial_inputs import (
    PlanPoint,
    PlanPose,
    PlanRectangle,
    PlanSegment,
    SpatialScene,
    SpatialSearch,
)
from fatebridge.core.fengshui.spatial_outputs import SearchReceipt
from fatebridge.core.fengshui.spatial_search import _dominates
from fatebridge.core.fengshui.spatial_visibility import _shadow
from tests.support.transports import SPECS, business, rest, surface_calls


class DeltaRow(TypedDict):
    left: float
    right: float
    expected: float


class DirectionRow(TypedDict):
    bearing: float
    radius: float
    expected_mask: int


class PrimitiveRow(TypedDict):
    angle: float
    point: list[float]
    origin: list[float]
    sine: float
    cosine: float
    transformed: list[float]
    inverse: list[float]
    ray_end: list[float]
    movement: float


class Composition(TypedDict):
    frame: float
    expected: float


class AngleRow(TypedDict):
    angle: float
    rectangle: list[list[float]]
    sweep: list[list[float]]
    heading_ray: list[float]
    heading: float
    compositions: list[Composition]


class VisibilityRow(TypedDict):
    target: list[list[float]]
    blockers: list[list[list[float]]]
    facing: float
    half_angle: float
    reach: float
    reference_qualification: str
    expected: int


class ShadowRow(TypedDict):
    footprint: list[list[float]]
    bottom: float
    top: float
    eye_height: float
    distance: float
    display: list[float]
    exact_expected_area: str


class GridRow(TypedDict):
    polygon: list[list[float]]
    origin: list[float]
    steps: list[float]
    expected_positions: list[list[float]]


class ParetoReference(TypedDict):
    vectors: list[list[float]]
    groups: list[list[list[float]]]
    dominance: list[str]
    fronts: list[list[int]]


class PublicControl(TypedDict):
    id: str
    key: str
    payload: dict[str, object]


class Reference(TypedDict):
    metadata: dict[str, object]
    delta: list[DeltaRow]
    directions: list[DirectionRow]
    primitive: list[PrimitiveRow]
    angles: list[AngleRow]
    visibility: list[VisibilityRow]
    shadows: list[ShadowRow]
    grids: list[GridRow]
    pareto: ParetoReference
    scene_seed: dict[str, object]
    public_controls: list[PublicControl]


class HeadingRow(TypedDict):
    start: list[float]
    end: list[float]
    group: str
    base: int | None
    offset: str | None
    masks: list[int] | None
    expected_float: float | None


class SegmentRow(TypedDict):
    point: list[float]
    start: list[float]
    end: list[float]
    group: str
    expected: bool


class HeadingControl(PublicControl):
    expected: dict[str, object]


class HeadingReference(TypedDict):
    metadata: dict[str, object]
    headings: list[HeadingRow]
    segments: list[SegmentRow]
    public_controls: list[HeadingControl]


@pytest.fixture(scope="module")
def heading_reference() -> HeadingReference:
    folder = Path(__file__).parents[1] / "data/fengshui_headings_cgal_v1"
    raw = gzip.decompress((folder / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (folder / "reference.json.sha256").read_text().strip()
    )
    result = TypeAdapter(HeadingReference).validate_json(raw)
    metadata = result["metadata"]
    assert metadata["fatebridge_imported"] is False
    assert metadata["cgal_version"] == "6.2.1"
    assert metadata["boost_decimal_digits"] == 120
    assert metadata["mpmath_decimal_digits"] == 1000
    assert metadata["numerical_crosschecks"] == 32014
    assert metadata["criteria_sha256"] == (
        "f36be5af87b34347bdf1cc879c58d75a37aa7ebe13cba31a6ac0ab8808892986"
    )
    return result


def test_point_pair_headings_against_independent_cgal_boost_and_mp1000(
    heading_reference: HeadingReference,
) -> None:
    qualified = undefined = 0
    assert len(heading_reference["headings"]) == 32018
    null_rows = [row for row in heading_reference["headings"] if row["base"] is None]
    qual_rows = [
        row for row in heading_reference["headings"] if row["base"] is not None
    ][::25]
    for i, row in enumerate([*null_rows, *qual_rows]):
        actual = geometry.heading(
            PlanPoint(x=row["start"][0], y=row["start"][1]),
            PlanPoint(x=row["end"][0], y=row["end"][1]),
        )
        if row["base"] is None:
            assert actual is None and row["offset"] is None and row["masks"] is None
            undefined += 1
            continue
        else:
            pass
        qualified += 1
        assert isinstance(actual, Fraction) and 0 <= actual < 360, (i, row)
        assert row["offset"] is not None
        offset = Fraction(row["offset"])
        expected = (row["base"] + offset) % 360
        error = abs(angles.angular_offset(actual, expected))
        assert error <= Fraction(2, 10**12), (i, row, error)
        assert error == 0 if offset == 0 else error <= abs(offset) / 10**80, (i, row)
        presented = float(actual)
        if presented == 360:
            presented = math.nextafter(360.0, 0.0)
        else:
            pass
        assert presented == row["expected_float"], (i, row)
        masks = row["masks"]
        assert masks is not None and len(masks) == 5
        for phase, radius, mask in (
            (actual, 0, masks[0]),
            (angles.compose_degrees(actual, 22.5), 0, masks[1]),
            (actual, 22.5, masks[2]),
        ):
            assert angles.direction_support(phase, radius) == [
                direction
                for k, direction in enumerate(angles.DIRECTIONS)
                if mask & (1 << k)
            ], (i, row, phase, radius)
        for radius, mask in zip((45, 90), masks[3:]):
            actual_mask = sum(
                1 << k
                for k in range(8)
                if abs(angles.angular_offset(actual, k * 45)) <= radius
            )
            assert actual_mask == mask, (i, row, radius, actual_mask)
    assert undefined == 4 and qualified == len(qual_rows)


def test_closed_segment_qualification_against_original_cgal(
    heading_reference: HeadingReference,
) -> None:
    assert len(heading_reference["segments"]) == 5120
    for i, row in enumerate(heading_reference["segments"]):
        actual = geometry.point_on_segment(
            PlanPoint(x=row["point"][0], y=row["point"][1]),
            PlanSegment(
                start=PlanPoint(x=row["start"][0], y=row["start"][1]),
                end=PlanPoint(x=row["end"][0], y=row["end"][1]),
            ),
        )
        assert actual is row["expected"], (i, row)


@pytest.mark.parametrize("control_index", range(28))
def test_public_heading_cells_and_undefined_views_remain_scoped(
    heading_reference: HeadingReference, control_index: int, surface_calls
) -> None:
    control = heading_reference["public_controls"][control_index]
    options = dict(
        fields=["layout_analysis.workstation_layout_analysis"],
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
    seat = branch["geometry"]["seats"][0]
    expected = control["expected"]
    for field in ("location_directions", "entrance_relative_positions"):
        if field in expected:
            assert seat[field] == expected[field], control["id"]
        else:
            pass
    if "entrance_visible" in expected:
        assert seat["form"]["entrance_visible"] is None
        receipt = branch["search"]["receipts"][0]
        assert receipt["physically_feasible"] is True
        assert receipt["status"] == "conditional_option"
        assert any(
            "entrance_visible" in key for key in receipt["pending_confirmations"]
        )
    else:
        pass
    if "screen_in_horizontal_view" in expected:
        assert branch["geometry"]["screen_visibility"][0]["in_horizontal_view"] is False
        assert branch["geometry"]["physically_feasible"] is False
    else:
        pass


@pytest.fixture(scope="module")
def reference() -> Reference:
    folder = Path(__file__).parents[1] / "data/fengshui_geometry_cgal_v1"
    raw = gzip.decompress((folder / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (folder / "reference.json.sha256").read_text().strip()
    )
    result = TypeAdapter(Reference).validate_json(raw)
    assert result["metadata"]["fatebridge_imported"] is False
    assert result["metadata"]["cgal_version"] == "6.2.1"
    assert result["metadata"]["criteria_sha256"] == (
        "97d2056c94666d99624ed733742b98f6e0b2918530f2799ec74a60ce07d32b47"
    )
    return result


def test_exact_angular_differences_and_closed_direction_support(
    reference: Reference,
) -> None:
    assert len(reference["delta"]) == 2965
    for i, row in enumerate(reference["delta"]):
        actual = angles.angular_delta(row["left"], row["right"])
        assert math.isfinite(actual) and actual == row["expected"], (i, row, actual)
        assert -180 <= actual < 180
    assert len(reference["directions"]) == 2107
    for i, row in enumerate(reference["directions"]):
        expected = [
            value
            for k, value in enumerate(angles.DIRECTIONS)
            if row["expected_mask"] & (1 << k)
        ]
        assert angles.direction_support(row["bearing"], row["radius"]) == expected, i


def test_fixed_mp90_coordinates_and_shapes(reference: Reference) -> None:
    assert len(reference["primitive"]) == 3010
    for i, row in enumerate(reference["primitive"]):
        point = PlanPoint(x=row["point"][0], y=row["point"][1])
        frame = PlanPose(
            center=PlanPoint(x=row["origin"][0], y=row["origin"][1]),
            rotation_degrees=row["angle"],
        )
        sine, cosine = angles._sin_cos_degrees(row["angle"])
        assert abs(sine - row["sine"]) <= 2e-15, i
        assert abs(cosine - row["cosine"]) <= 2e-15, i
        world = geometry.transform_point(point, frame)
        assert abs(world.x - row["transformed"][0]) <= 2e-12, i
        assert abs(world.y - row["transformed"][1]) <= 2e-12, i
        local = geometry.inverse_point(point, frame)
        assert abs(local.x - row["inverse"][0]) <= 2e-12, i
        assert abs(local.y - row["inverse"][1]) <= 2e-12, i
        ray = geometry.ray_xy(frame.center, row["angle"], 2)
        assert abs(ray.coords[1][0] - row["ray_end"][0]) <= 2e-12, i
        assert abs(ray.coords[1][1] - row["ray_end"][1]) <= 2e-12, i
        assert (
            abs(
                geometry.movement_distance(PlanPose(center=point), frame)
                - row["movement"]
            )
            <= 2e-12
        ), i
    assert len(reference["angles"]) == 301
    for i, row in enumerate(reference["angles"]):
        rectangle = PlanRectangle(
            center=PlanPoint(x=5.25, y=-10.5),
            rotation_degrees=row["angle"],
            width_m=1.6,
            depth_m=0.8,
        )
        actual = list(geometry.rectangle_xy(rectangle).exterior.coords)[:-1]
        assert len(actual) == 4
        for x, y in actual:
            assert (
                min(max(abs(x - e[0]), abs(y - e[1])) for e in row["rectangle"])
                <= 2e-12
            ), i
        segment = PlanSegment(start=PlanPoint(x=0, y=0), end=PlanPoint(x=2, y=0))
        sweep = list(geometry.swept_segment(segment, row["angle"], 2).exterior.coords)[
            :-1
        ]
        assert len(sweep) == 4
        for point, expected in zip(sweep, row["sweep"]):
            assert max(abs(p - e) for p, e in zip(point, expected)) <= 2e-12, i
        actual_heading = geometry.heading(
            PlanPoint(x=0, y=0),
            PlanPoint(x=row["heading_ray"][0], y=row["heading_ray"][1]),
        )
        assert 0 <= actual_heading < 360
        error = (Fraction(actual_heading) - Fraction(row["heading"]) + 180) % 360 - 180
        assert abs(error) <= 2e-12, i
        for composition in row["compositions"]:
            result = geometry.transform_rectangle(
                rectangle,
                PlanPose(
                    center=PlanPoint(x=0, y=0),
                    rotation_degrees=composition["frame"],
                ),
            )
            error = (
                Fraction(result.rotation_degrees)
                - Fraction(composition["expected"])
                + 180
            ) % 360 - 180
            assert abs(error) <= 2e-12, (i, composition)


def test_cgal_rotational_sweep_visibility_including_target_crossings(
    reference: Reference,
) -> None:
    assert len(reference["visibility"]) == 10450
    qualified = invalid = 0
    invalid_rows = [row for row in reference["visibility"] if row["expected"] == -1]
    qual_rows = [row for row in reference["visibility"] if row["expected"] != -1][::20]
    for i, row in enumerate([*invalid_rows, *qual_rows]):
        if row["expected"] == -1:
            assert row["reference_qualification"].startswith("invalid_observer_")
            invalid += 1
            continue
        else:
            pass
        qualified += 1
        assert row["reference_qualification"] == "observer0outsideallblockersandtarget"
        target = row["target"]
        actual = geometry.entrance_visible(
            PlanPoint(x=0, y=0),
            row["facing"],
            row["half_angle"],
            PlanSegment(
                start=PlanPoint(x=target[0][0], y=target[0][1]),
                end=PlanPoint(x=target[1][0], y=target[1][1]),
            ),
            [Polygon(p) for p in row["blockers"]],
            row["reach"],
        )
        assert actual is bool(row["expected"]), (i, row)
    assert invalid == 2 and qualified == len(qual_rows)


def test_cgal_exact_convex_hull_prism_shadow_areas(reference: Reference) -> None:
    assert len(reference["shadows"]) == 1484
    for i, row in enumerate(reference["shadows"]):
        expected = float(Fraction(row["exact_expected_area"]))
        display = box(*row["display"])
        actual = _shadow(
            Polygon(row["footprint"]),
            row["bottom"],
            row["top"],
            PlanPoint(x=0, y=0),
            row["eye_height"],
            (1, 0),
            (0, 1),
            row["distance"],
            display,
        )
        assert abs(actual.area - expected) <= 2e-12 * max(1, display.area), (i, row)


def test_cgal_containment_of_decimal_grid_centers(reference: Reference) -> None:
    assert len(reference["grids"]) == 27
    for i, row in enumerate(reference["grids"]):
        data = deepcopy(reference["scene_seed"])
        data["boundary"] = {"vertices": [dict(x=x, y=y) for x, y in row["polygon"]]}
        scene = SpatialScene.model_validate(data)
        search = SpatialSearch.model_validate(
            dict(
                domains=[
                    dict(
                        object_id="desk",
                        grid=dict(
                            origin=dict(x=row["origin"][0], y=row["origin"][1]),
                            step_x_m=row["steps"][0],
                            step_y_m=row["steps"][1],
                            center_region=data["boundary"],
                        ),
                        rotations_degrees=[0],
                    )
                ]
            )
        )
        result = resolve_search_domains(scene, search)[0]
        assert [[p.x, p.y] for p in result.positions] == row["expected_positions"], i
        assert result.coordinate_frame == scene.frame_id


def test_original_deap_dominance_and_fronts_preserve_unknown_incomparability(
    reference: Reference,
) -> None:
    source = reference["pareto"]
    receipts = [
        SearchReceipt(
            candidate_id=str(i),
            poses={},
            physically_feasible=True,
            status="ready",
            blocking_reasons=[],
            pending_confirmations=[],
            rule_dimensions={"a": int(v[3]), "b": int(v[4])},
            changed_object_count=int(v[0]),
            movement_m=v[1],
            rotation_degrees=v[2],
        )
        for i, v in enumerate(source["vectors"])
    ]
    assert len(receipts) == 108
    for i, left in enumerate(receipts):
        for j, right in enumerate(receipts):
            assert _dominates(left, right) is (source["dominance"][i][j] == "1")
        unknown = left.model_copy(
            update={"rule_dimensions": {"a": None, "b": left.rule_dimensions["b"]}}
        )
        assert not _dominates(left, unknown)
        assert not _dominates(unknown, left)
        assert not _dominates(unknown, unknown)
    assert len(source["groups"]) == len(source["fronts"]) == 64
    for group, expected in zip(source["groups"], source["fronts"]):
        candidates = [receipts[source["vectors"].index(v)] for v in group]
        actual = [
            i
            for i, candidate in enumerate(candidates)
            if not any(_dominates(other, candidate) for other in candidates)
        ]
        assert actual == expected


@pytest.mark.parametrize("control_index", range(3))
def test_public_geometry_facts_control_search_and_explicit_permissions(
    reference: Reference, control_index: int, surface_calls
) -> None:
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
        SPECS["fengshui_assess"],
        control["payload"],
        params=options,
        options=options,
        flags=(
            "--fields",
            *fields,
            "--strict-fields",
            "--response-char-limit",
            "0",
            "--include-snapshot-text",
            "false",
            "--as-of",
            options["as_of"],
        ),
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    actual = business(response.json())
    assert actual == business(cli) == business(protocol.structured_content)
    branch = actual["layout_analysis"]["workstation_layout_analysis"]
    assert branch["geometry"]["physically_feasible"] is True
    receipt = branch["search"]["receipts"][0]
    if control["id"].startswith("entrance-"):
        assert branch["geometry"]["seats"][0]["form"]["entrance_visible"] is True
        assert receipt["status"] == "ready"
        assert branch["search"]["returned_candidate_ids"] == ["spatial-0001"]
    else:
        assert receipt["status"] == "blocked"
        assert "permission:desk:can_rotate" in receipt["blocking_reasons"]
        assert receipt["changed_object_count"] == 1
        assert receipt["rotation_degrees"] == 1e-14
        assert branch["search"]["returned_candidate_ids"] == []
