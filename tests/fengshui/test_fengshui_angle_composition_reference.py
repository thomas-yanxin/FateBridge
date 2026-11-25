"""Independent exact phases, composed frames and actual permission controls."""

import gzip
import hashlib
import math
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.fengshui import spatial_angles as angles
from fatebridge.core.fengshui import spatial_geometry as geometry
from fatebridge.core.fengshui.spatial_inputs import PlanPoint, PlanPose, PlanRectangle
from tests.support.transports import SPECS, business, rest, surface_calls


class BoostProof(TypedDict):
    cases: int
    component_comparisons: int
    binary64_disagreements: int
    no_product_import: bool


class Metadata(TypedDict):
    fatebridge_imported: bool
    cgal_version: str
    criteria_sha256: str
    boost_trig: BoostProof


class Composition(TypedDict):
    terms: list[float]
    sine: float
    cosine: float
    expected_phase: str
    radii: list[float]
    direction_masks: list[int]
    origin: list[float]
    point: list[float]
    width: float
    depth: float
    exact_point: list[str]
    exact_corners: list[list[str]]
    exact_inverse: list[str]


class Change(TypedDict):
    before: list[float]
    after: list[float]
    exact_delta: str
    expected_changed: bool


class PublicControl(TypedDict):
    id: str
    key: str
    payload: dict[str, object]
    expect_final_error: bool


class Reference(TypedDict):
    metadata: Metadata
    compositions: list[Composition]
    changes: list[Change]
    public_controls: list[PublicControl]


@pytest.fixture(scope="module")
def reference() -> Reference:
    folder = Path(__file__).parents[1] / "data/fengshui_angles_cgal_v1"
    raw = gzip.decompress((folder / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (folder / "reference.json.sha256").read_text().strip()
    )
    result = TypeAdapter(Reference).validate_json(raw)
    assert result["metadata"]["fatebridge_imported"] is False
    assert result["metadata"]["cgal_version"] == "6.2.1"
    assert result["metadata"]["criteria_sha256"] == (
        "92359988ea34c7ec0b554375472ddb2e2b703157358cbcf53a290b41bb19c4bc"
    )
    proof = result["metadata"]["boost_trig"]
    assert proof["cases"] == 4397 and proof["component_comparisons"] == 8794
    assert proof["binary64_disagreements"] == 0 and proof["no_product_import"]
    return result


def test_original_frame_chains_preserve_every_exact_periodic_phase(
    reference: Reference,
) -> None:
    assert len(reference["compositions"]) == 4397
    for i, row in enumerate(reference["compositions"]):
        expected = Fraction(row["expected_phase"])
        assert angles.compose_degrees(*row["terms"]) == expected, (i, row)
        frame: PlanRectangle | geometry.GeometryRectangle = PlanRectangle(
            center=PlanPoint(x=0, y=0),
            rotation_degrees=row["terms"][0],
            width_m=row["width"],
            depth_m=row["depth"],
        )
        for term in row["terms"][1:]:
            frame = geometry.transform_rectangle(
                frame, PlanPose(center=PlanPoint(x=0, y=0), rotation_degrees=term)
            )
        assert Fraction(frame.rotation_degrees) % 360 == expected, (i, row)


def test_components_match_independent_boost120_and_mp700_including_tiny_offsets(
    reference: Reference,
) -> None:
    for i, row in enumerate(reference["compositions"]):
        sine, cosine = angles._sin_cos_degrees(Fraction(row["expected_phase"]))
        for actual, expected in ((sine, row["sine"]), (cosine, row["cosine"])):
            error = abs(actual - expected)
            assert error <= 2e-15, (i, row, actual, expected)
            if abs(expected) < 1e-8:
                assert error <= 4 * math.ulp(expected), (i, row, actual, expected)
            else:
                pass


def test_all_exact_composed_closed_direction_intervals(reference: Reference) -> None:
    count = 0
    for i, row in enumerate(reference["compositions"]):
        phase = angles.compose_degrees(*row["terms"])
        assert len(row["radii"]) == len(row["direction_masks"]) == 7
        for radius, expected in zip(row["radii"], row["direction_masks"]):
            actual = angles.direction_support(phase, radius)
            assert actual == [
                d for k, d in enumerate(angles.DIRECTIONS) if expected & (1 << k)
            ], (i, row, radius, actual)
            count += 1
    assert count == 30779


def test_attached_rotation_arithmetic_preserves_exact_nonzero_changes(
    reference: Reference,
) -> None:
    assert len(reference["changes"]) == 14660
    for i, row in enumerate(reference["changes"]):
        before, after = (
            angles.compose_degrees(*row["before"]),
            angles.compose_degrees(*row["after"]),
        )
        actual = angles.angular_delta(after, before)
        expected = float(Fraction(row["exact_delta"]))
        if expected == 180:
            expected = math.nextafter(180.0, 0.0)
        else:
            pass
        assert actual == expected, (i, row, actual)
        assert (actual != 0) is row["expected_changed"], (i, row, actual)


def test_composed_affine_points_rectangle_vertices_and_actual_cgal_inverse(
    reference: Reference,
) -> None:
    for i, row in enumerate(reference["compositions"]):
        frame = geometry.GeometryRectangle(
            center=PlanPoint(x=row["origin"][0], y=row["origin"][1]),
            rotation_degrees=Fraction(row["expected_phase"]),
            width_m=row["width"],
            depth_m=row["depth"],
        )
        point = PlanPoint(x=row["point"][0], y=row["point"][1])
        actual = geometry.transform_point(point, frame)
        expected = [float(Fraction(v)) for v in row["exact_point"]]
        assert max(abs(actual.x - expected[0]), abs(actual.y - expected[1])) <= 2e-12, i
        local = geometry.inverse_point(point, frame)
        expected = [float(Fraction(v)) for v in row["exact_inverse"]]
        assert max(abs(local.x - expected[0]), abs(local.y - expected[1])) <= 2e-12, i
        polygon = geometry.rectangle_xy(frame)
        vertices = list(polygon.exterior.coords)[:-1]
        expected_vertices = [
            [float(Fraction(v)) for v in point] for point in row["exact_corners"]
        ]
        assert len(vertices) == len(expected_vertices) == 4
        for x, y in vertices:
            assert (
                min(max(abs(x - px), abs(y - py)) for px, py in expected_vertices)
                <= 2e-12
            ), (i, row, vertices)


@pytest.mark.parametrize("control_index", range(28))
def test_public_angle_facts_search_permissions_and_invalid_axis_retention(
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
        SPECS["fengshui_assess"], control["payload"], projection=options
    )
    if control["expect_final_error"]:
        assert response.status_code == 422 and code != 0 and protocol.is_error
        for result in (response.json(), cli, protocol.structured_content):
            assert result["error_code"] == "validation_error"
            assert result["retryable"] is False
        return
    else:
        pass
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    actual = business(response.json())
    assert actual == business(cli) == business(protocol.structured_content)
    branch = actual["layout_analysis"]["workstation_layout_analysis"]
    seat = branch["geometry"]["seats"][0]
    assert 0 <= seat["plan_facing_degrees"] < 360
    name = control["id"]
    if name in ("open-0", "open-1"):
        assert seat["form"]["solid_backing"] is True
        assert seat["backing_distance_m"] == 1
    elif name in ("open-2", "open-3"):
        assert seat["plan_facing_degrees"] == (256 if name == "open-2" else 104)
    elif name.startswith("closed-sector-"):
        assert seat["facing_directions"] == (["N"] if "--" in name else ["NE"])
    elif name.startswith("attached-"):
        receipt = branch["search"]["receipts"][0]
        if name.endswith("-False"):
            assert receipt["status"] == "blocked"
            assert (
                "attached_locked_item:display:can_rotate" in receipt["blocking_reasons"]
            )
        elif name.endswith("-None"):
            assert receipt["status"] == "conditional_option"
            assert (
                "layout_constraints.display.can_rotate"
                in receipt["pending_confirmations"]
            )
        else:
            assert receipt["status"] == "ready"
    elif name == "distinct-tiny-negative-search-rotations":
        assert branch["search"]["evaluated_count"] == 2
        assert len(branch["search"]["receipts"]) == 2
    elif name.startswith("supp-desktop-compass-outer-branch-"):
        placement = next(
            row
            for row in branch["geometry"]["desktop_placements"]
            if row["object_id"] == "display"
        )
        # The old outer-circle snapshot also included W/NW or SW. Whole-
        # footprint support is narrower. Prove this rectangle stays inside
        # one cell using atan(q)<q and pi>3, independently of the new reducer.
        scene = control["payload"]["workstation_layout"]["scene"]
        desk = scene["bodies"][0]["footprint"]
        item = scene["desktops"][0]["items"][0]["footprint"]
        assert item["center"]["y"] == 0 and item.get("rotation_degrees", 0) == 0
        phase = (
            Fraction(desk["rotation_degrees"])
            + Fraction(scene["compass"]["y_axis_bearing_degrees"])
            + 90
        ) % 360
        expected_center = 180 if name.endswith("--1") else 0
        delta = (phase - expected_center + 180) % 360 - 180
        angular_bound = (
            60
            * (Fraction(item["depth_m"]) / 2)
            / (Fraction(item["center"]["x"]) - Fraction(item["width_m"]) / 2)
        )
        assert abs(delta) + angular_bound < Fraction(45, 2)
        assert placement["compass_directions"] == (
            ["S"] if expected_center == 180 else ["N"]
        )
    elif name.startswith("supp-actual-seated-metal-"):
        rule = next(
            row
            for row in branch["rule_comparisons"]
            if row["rule_id"] == "wofs_desktop_compass_v1.same_desk_metal_equipment"
        )
        assert rule["matches"] is ("--" in name)
        assert rule["reference_frame"] == "seated_right_with_higher_left_object"
    else:
        pass
