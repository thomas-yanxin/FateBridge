"""Measured planar scenes and finite search domains, independent of lineages."""

from math import cos, hypot, radians, remainder, sin
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    model_validator,
)
from shapely.geometry import Polygon

from .numeric_inputs import FengshuiInput
from .workstation_inputs import ObservedCondition

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")]
Evidence = Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S")]
Number = Annotated[float, Field(allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
ObservationBasis = Literal["measured", "user_confirmed", "image_observed"]
CompassDirection = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
RelativePosition = Literal[
    "front",
    "front_right",
    "right",
    "back_right",
    "back",
    "back_left",
    "left",
    "front_left",
]


class PlanPoint(FengshuiInput):
    x: Number
    y: Number


class PlanSegment(FengshuiInput):
    start: PlanPoint
    end: PlanPoint

    @model_validator(mode="after")
    def nonzero(self) -> "PlanSegment":
        if self.start == self.end:
            raise ValueError("线段两端不能重合")
        return self


class PlanPolygon(FengshuiInput):
    vertices: list[PlanPoint] = Field(min_length=3, max_length=100)

    @model_validator(mode="after")
    def simple_polygon(self) -> "PlanPolygon":
        polygon = Polygon([(p.x, p.y) for p in self.vertices])
        if not polygon.is_valid or polygon.area == 0:
            raise ValueError("平面多边形须有面积、无自交；不自动修复或改变边界")
        return self


class PlanPose(FengshuiInput):
    center: PlanPoint
    rotation_degrees: Number = Field(
        default=0, description="相对图纸+y顺时针；局部+x为右，+y为远离坐者"
    )


class PlanRectangle(PlanPose):
    width_m: Positive
    depth_m: Positive


class CompassBinding(FengshuiInput):
    y_axis_bearing_degrees: Number
    north_reference: Literal["magnetic", "true"]
    uncertainty_degrees: Number = Field(ge=0, le=180)
    sector_origin: PlanPoint
    reference_scope: Literal["house", "floor", "room", "workstation"]
    chart_binding_confirmed: StrictBool = Field(
        description="明确确认该立极、范围、北基准与本次所选宅/年/月盘一致；不自动定中心或套小太极"
    )
    evidence: Evidence


class SandWaterObservation(FengshuiInput):
    classification: Literal["sand", "water", "mixed", "unknown"]
    observation_basis: ObservationBasis
    evidence: Evidence


class SpatialBody(FengshuiInput):
    object_id: Identifier
    kind: Literal["desk", "furniture", "screen", "plant", "pillar", "beam"]
    footprint: PlanRectangle
    bottom_m: Number = Field(ge=0)
    top_m: Positive
    blocks_view: StrictBool
    has_sharp_corners: StrictBool | None = Field(
        default=None,
        description="独立确认是否为本次作者规则所指实体尖角；不由矩形包络猜测",
    )
    sand_water: SandWaterObservation | None = Field(
        default=None, description="独立确认砂水分类；不能由几何高低或物件名称推断"
    )

    @model_validator(mode="after")
    def height_interval(self) -> "SpatialBody":
        if self.top_m <= self.bottom_m:
            raise ValueError("物件顶面须高于底面；平面投影与高度分别计算")
        return self


class SpatialOpening(FengshuiInput):
    object_id: Identifier
    kind: Literal["entrance", "window", "bathroom_door", "staircase"]
    segment: PlanSegment
    inward_degrees: Number | None = Field(
        default=None, description="实际入口向室内的直线方向，相对图纸+y顺时针"
    )

    @model_validator(mode="after")
    def entrance_axis(self) -> "SpatialOpening":
        if self.kind == "entrance" and self.inward_degrees is None:
            raise ValueError("实际入口须明确向内方向；不能用坐者朝向代替")
        if self.inward_degrees is not None:
            dx, dy = (
                self.segment.end.x - self.segment.start.x,
                self.segment.end.y - self.segment.start.y,
            )
            angle = radians(self.inward_degrees)
            if abs(dx * sin(angle) + dy * cos(angle)) > 1e-8 * hypot(dx, dy):
                raise ValueError("入口向内方向须垂直于门洞线段")
        return self


class SpatialPassage(FengshuiInput):
    object_id: Identifier
    centerline: PlanSegment = Field(description="start到end为走道进入工位的方向")
    width_m: Positive


class WorkSeat(FengshuiInput):
    desk_id: Identifier
    subject_ids: list[Identifier] | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="可选绑定本次已提供的实际使用人；省略沿用全部使用人的既有合同，不从座位猜身份",
    )
    offset: PlanPoint = Field(description="相对书桌中心的局部米坐标；近侧为-y")
    facing_offset_degrees: Number = 0
    body_width_m: Positive
    body_depth_m: Positive
    eye_height_m: Positive
    head_height_m: Positive
    view_half_angle_degrees: Positive = Field(
        le=90, description="用户明确的正常正面视野工程模型；不是传统吉凶阈值"
    )
    operating_zone: PlanRectangle = Field(
        description="书桌局部坐标中的地面椅位/活动净空；独立于桌面键盘区"
    )
    entrance_id: Identifier | None = None
    window_id: Identifier | None = Field(
        default=None, description="多窗时须明确本次核对的窗；不任取第一扇"
    )
    activity: Literal["work", "study", "meditation", "storage", "mixed", "unknown"]
    sector_anchor: Literal["seat", "desk_center"] = Field(
        description="明确按实际坐者还是桌中心关联落宫，不能相互替代"
    )

    @model_validator(mode="after")
    def eye_below_head(self) -> "WorkSeat":
        if self.eye_height_m >= self.head_height_m:
            raise ValueError("坐者眼高须低于头顶高度，两者独立于家具高度")
        if self.subject_ids is not None and len(self.subject_ids) != len(
            set(self.subject_ids)
        ):
            raise ValueError("同一工位使用人不能重复")
        return self


DesktopRepresentation = Literal[
    "living_plant",
    "fresh_flowers",
    "lamp",
    "smooth_crystal_ball",
    "metal_office_equipment",
    "water_image",
    "dark_accessory",
    "other",
    "unknown",
]


class VerticalScreen(FengshuiInput):
    center: PlanPoint = Field(description="显示面中心的水平投影，相对物件局部坐标")
    front_degrees: Number = Field(
        description="显示面朝向观察者的水平法线，相对物件+y顺时针"
    )
    width_m: Positive
    height_m: Positive
    bottom_above_desktop_m: Number = Field(ge=0)
    required_visible: StrictBool = Field(
        description="是否将整块显示面无遮挡且在声明水平视野内作为候选硬约束"
    )


class DesktopObject(FengshuiInput):
    object_id: Identifier
    footprint: PlanRectangle = Field(description="相对桌面中心，局部+x右、+y远")
    height_m: Positive
    blocks_view: StrictBool
    representation: DesktopRepresentation
    representation_basis: ObservationBasis
    evidence: Evidence
    screen: VerticalScreen | None = Field(
        default=None, description="独立实测的竖直显示面；不由设备名称猜尺寸、朝向或眩光"
    )
    healthy: ObservedCondition | None = Field(
        default=None,
        description="植物/鲜花状态的独立事实；位置与活植物身份不证明状态良好",
    )

    @model_validator(mode="after")
    def plant_condition(self) -> "DesktopObject":
        if self.healthy is not None and self.representation not in {
            "living_plant",
            "fresh_flowers",
        }:
            raise ValueError("植物/鲜花状态条件不能套到其他物件")
        if self.screen is not None:
            screen = self.screen
            if screen.bottom_above_desktop_m + screen.height_m > self.height_m:
                raise ValueError("显示面须包含在所登记物件的完整高度包络内")
            angle = radians(remainder(screen.front_degrees, 360))
            for sign in (-1, 1):
                x = screen.center.x + sign * screen.width_m / 2 * cos(angle)
                y = screen.center.y - sign * screen.width_m / 2 * sin(angle)
                if (
                    abs(x) > self.footprint.width_m / 2 + 1e-10
                    or abs(y) > self.footprint.depth_m / 2 + 1e-10
                ):
                    raise ValueError("显示面须包含在所登记物件的完整水平包络内")
        return self


class MeasuredDesktop(FengshuiInput):
    desk_id: Identifier
    ruleset_ids: list[Literal["desktop_bagua_btb_v1", "wofs_desktop_compass_v1"]] = (
        Field(
            default_factory=list,
            max_length=2,
            description="逐个显式另选；不默认开启BTB或罗盘桌面处方",
        )
    )
    goal: Literal["career", "abundance"] = "career"
    items: list[DesktopObject] = Field(default_factory=list, max_length=30)
    protected_zones: list[PlanPolygon] = Field(
        default_factory=list,
        max_length=20,
        description="桌面局部坐标的键盘/书写/屏幕等保留区",
    )


class SpatialScene(FengshuiInput):
    frame_id: Identifier
    units: Literal["m"] = "m"
    boundary: PlanPolygon
    observation_basis: ObservationBasis
    evidence: Evidence
    inventory_confirmed: StrictBool = Field(
        description="确认本次空间对象/门窗/通道/梁/背靠清单完整；false时缺项保持未知，普通解释可先进行"
    )
    coordinate_uncertainty_m: Number = Field(
        default=0,
        ge=0,
        description="坐标误差半径；0仅表示按所给坐标计算，不认证测量仪器精度",
    )
    compass: CompassBinding | None = None
    bodies: list[SpatialBody] = Field(min_length=1, max_length=100)
    openings: list[SpatialOpening] = Field(default_factory=list, max_length=30)
    passages: list[SpatialPassage] = Field(default_factory=list, max_length=30)
    solid_backing_segments: list[PlanSegment] = Field(
        default_factory=list, max_length=50
    )
    keep_clear_zones: list[PlanPolygon] = Field(default_factory=list, max_length=30)
    seats: list[WorkSeat] = Field(min_length=1, max_length=20)
    desktops: list[MeasuredDesktop] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def identities(self) -> "SpatialScene":
        ids = [b.object_id for b in self.bodies] + [o.object_id for o in self.openings]
        ids += [p.object_id for p in self.passages]
        ids += [item.object_id for desktop in self.desktops for item in desktop.items]
        if len(ids) != len(set(ids)):
            raise ValueError("空间对象ID须全局唯一")
        desks = {b.object_id for b in self.bodies if b.kind == "desk"}
        for references in (
            [s.desk_id for s in self.seats],
            [d.desk_id for d in self.desktops],
        ):
            if len(references) != len(set(references)) or set(references) - desks:
                raise ValueError("坐者/桌面须唯一关联明确的书桌")
        entries = {o.object_id for o in self.openings if o.kind == "entrance"}
        if any(
            s.entrance_id is not None and s.entrance_id not in entries
            for s in self.seats
        ):
            raise ValueError("坐者入口须引用实际entrance，不能用窗/厕门/走道代替")
        windows = {o.object_id for o in self.openings if o.kind == "window"}
        if any(
            s.window_id is not None and s.window_id not in windows for s in self.seats
        ):
            raise ValueError("坐者窗须引用明确window")
        for desktop in self.desktops:
            if len(desktop.ruleset_ids) != len(set(desktop.ruleset_ids)):
                raise ValueError("桌面规则版本不能重复")
            if any(
                i.screen is not None for i in desktop.items
            ) and desktop.desk_id not in {s.desk_id for s in self.seats}:
                raise ValueError("显示面视线须关联同桌实际坐者及眼高")
        return self


class SpatialGrid(FengshuiInput):
    origin: PlanPoint
    step_x_m: Positive
    step_y_m: Positive
    center_region: PlanPolygon | None = Field(
        default=None,
        description="可选中心搜索区；省略时家具用场景边界，桌面物件用所属桌面。坐标沿用对象所属参考系",
    )


class ResolvedMoveDomain(BaseModel):
    model_config = ConfigDict(frozen=True)
    object_id: str
    positions: tuple[PlanPoint, ...]
    rotations_degrees: tuple[float, ...]
    input_kind: Literal["explicit", "grid"]
    coordinate_frame: str


class SpatialMoveDomain(FengshuiInput):
    object_id: Identifier
    positions: list[PlanPoint] | None = Field(default=None, min_length=1, max_length=30)
    grid: SpatialGrid | None = None
    rotations_degrees: list[Number] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def unique_poses(self) -> "SpatialMoveDomain":
        if (self.positions is None) == (self.grid is None):
            raise ValueError("位置须在显式positions与自动grid中二选一")
        if self.positions is not None and len(
            {(p.x, p.y) for p in self.positions}
        ) != len(self.positions):
            raise ValueError("搜索位置不能重复")
        if len({r % 360 for r in self.rotations_degrees}) != len(
            self.rotations_degrees
        ):
            raise ValueError("搜索角度归一化后不能重复")
        return self


class SpatialSearch(FengshuiInput):
    domains: list[SpatialMoveDomain] = Field(min_length=1, max_length=6)
    max_results: int = Field(default=10, ge=1, le=50)
    required_checks: list[
        Literal[
            "entrance_visible",
            "no_entry_direct_line",
            "no_passage_direct_line",
            "no_overhead_beam",
            "no_sharp_corner",
            "solid_backing",
        ]
    ] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def finite_search(self) -> "SpatialSearch":
        ids = [d.object_id for d in self.domains]
        if len(ids) != len(set(ids)):
            raise ValueError("每个搜索对象只定义一个完整位置/角度域")
        if len(self.required_checks) != len(set(self.required_checks)):
            raise ValueError("搜索条件不能重复")
        return self
