"""Independent footprint support and its public author-rule propagation."""

import gzip
import hashlib
import json
from pathlib import Path

from shapely.geometry import Polygon

from fatebridge.core.fengshui.spatial_geometry import footprint_direction_support
from fatebridge.core.fengshui.spatial_inputs import PlanPoint, SpatialScene
from fatebridge.core.fengshui.spatial_scene import location_support
from fatebridge.services.fengshui import assess

FOLDER = Path(__file__).parents[1] / "data/fengshui_footprint_cgal_v1"
RAW = gzip.decompress((FOLDER / "reference.json.gz").read_bytes())
REFERENCE = json.loads(RAW)


def test_convex_footprint_support_matches_all_fixed_exact_CGAL_arguments():
    assert (
        hashlib.sha256(RAW).hexdigest()
        == (FOLDER / "reference.json.sha256").read_text().strip()
    )
    rows = [r for r in REFERENCE["rows"] if r["kind"] == "polygon"]
    assert len(rows) == 3265
    for row in rows:
        assert (
            footprint_direction_support(
                Polygon(row["vertices"]),
                row["frame_index"] * 22.5,
                row["coordinate_error"],
                row["compass_error_index"] * 22.5,
            )
            == row["expected"]
        ), row["id"]


def test_point_error_support_retains_all_fixed_closed_tangencies():
    template = json.loads(
        Path("docs/examples/fengshui-workstation-measured.json").read_text()
    )
    scene = SpatialScene.model_validate(template["workstation_layout"]["scene"])
    assert scene.compass is not None
    rows = [r for r in REFERENCE["rows"] if r["kind"] == "point"]
    assert len(rows) == 512
    for row in rows:
        bound = scene.model_copy(
            update={
                "coordinate_uncertainty_m": row["coordinate_error"],
                "compass": scene.compass.model_copy(
                    update={
                        "sector_origin": PlanPoint(x=0, y=0),
                        "y_axis_bearing_degrees": row["frame_index"] * 22.5,
                        "uncertainty_degrees": row["compass_error_index"] * 22.5,
                    }
                ),
            }
        )
        assert (
            location_support(
                bound, PlanPoint(x=row["vertices"][0][0], y=row["vertices"][0][1])
            )
            == row["expected"]
        ), row["id"]


def test_whole_north_footprint_excludes_southeast_without_inventing_a_score():
    request = json.loads(
        Path("docs/examples/fengshui-workstation-measured.json").read_text()
    )
    request["workstation_layout"].pop("search")
    scene = request["workstation_layout"]["scene"]
    scene["compass"].update(y_axis_bearing_degrees=0, uncertainty_degrees=0)
    scene["desktops"][0]["items"][0]["footprint"] = {
        "center": {"x": 0, "y": 0.1},
        "width_m": 0.4,
        "depth_m": 0.01,
        "rotation_degrees": 0,
    }
    branch = assess(**request)["layout_analysis"]["workstation_layout_analysis"]
    assert branch["geometry"]["desktop_placements"][0]["compass_directions"] == [
        "N",
        "NE",
        "NW",
    ]
    rule = next(
        r
        for r in branch["rule_comparisons"]
        if r["rule_id"] == "wofs_desktop_compass_v1.plant_southeast"
    )
    assert rule["matches"] is False and rule["candidate_only"] is False
    assert rule["reference_frame"] == "desktop_compass_not_house_palace"
    assert branch["research_completion_status"] == "incomplete"
