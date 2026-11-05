"""Resolve explicit lattices once at the request boundary, before enumeration."""

from fractions import Fraction
from math import ceil, floor, prod

from shapely.geometry import Point, box

from .spatial_geometry import polygon_xy
from .spatial_inputs import PlanPoint, ResolvedMoveDomain, SpatialScene, SpatialSearch


def resolve_search_domains(
    scene: SpatialScene, search: SpatialSearch
) -> list[ResolvedMoveDomain]:
    bodies = {b.object_id: b for b in scene.bodies}
    item_desks = {i.object_id: d.desk_id for d in scene.desktops for i in d.items}
    resolved = []
    for domain in search.domains:
        desk_id = item_desks.get(domain.object_id)
        frame = f"desktop:{desk_id}" if desk_id else scene.frame_id
        positions = domain.positions
        if domain.grid is not None:
            grid = domain.grid
            if grid.center_region is not None:
                region = polygon_xy(grid.center_region)
            elif desk_id:
                desk = bodies[desk_id].footprint
                region = box(
                    -desk.width_m / 2,
                    -desk.depth_m / 2,
                    desk.width_m / 2,
                    desk.depth_m / 2,
                )
            else:
                region = polygon_xy(scene.boundary)
            xmin, ymin, xmax, ymax = region.bounds
            # Decimal arithmetic keeps edges such as .3/.1 inclusive.
            ox, oy = Fraction(str(grid.origin.x)), Fraction(str(grid.origin.y))
            sx, sy = Fraction(str(grid.step_x_m)), Fraction(str(grid.step_y_m))
            ix0, ix1 = ceil((Fraction(str(xmin)) - ox) / sx), floor(
                (Fraction(str(xmax)) - ox) / sx
            )
            iy0, iy1 = ceil((Fraction(str(ymin)) - oy) / sy), floor(
                (Fraction(str(ymax)) - oy) / sy
            )
            if max(0, ix1 - ix0 + 1) * max(0, iy1 - iy0 + 1) > 4096:
                raise ValueError(
                    "每个网格包围盒最多4096个采样点；请增大显式步长或缩小中心搜索区"
                )
            positions = []
            for iy in range(iy0, iy1 + 1):
                for ix in range(ix0, ix1 + 1):
                    x, y = float(ox + ix * sx), float(oy + iy * sy)
                    if region.covers(Point(x, y)):
                        positions.append(PlanPoint(x=x, y=y))
            if not positions:
                raise ValueError(
                    "声明的网格没有落在中心搜索区内的点；不自动移动原点或改变步长"
                )
        # The input XOR validator guarantees one of explicit positions or grid.
        assert positions is not None
        resolved.append(
            ResolvedMoveDomain(
                object_id=domain.object_id,
                positions=tuple(positions),
                rotations_degrees=tuple(domain.rotations_degrees),
                input_kind="grid" if domain.grid is not None else "explicit",
                coordinate_frame=frame,
            )
        )
    if prod(len(d.positions) * len(d.rotations_degrees) for d in resolved) > 4096:
        raise ValueError("搜索空间最多4096个完整组合；请缩小位置/角度域或增大网格步长")
    return resolved
