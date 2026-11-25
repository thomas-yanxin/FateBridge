"""Heluo charts, local geometry and combined Sanshi outputs."""

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import (
    AnalysisContext,
    CalendarContext,
    FourPillars,
    Object,
)
from fatebridge.core.contracts.output_heluo_qi import HeluoYuantangDerivation
from fatebridge.core.contracts.output_liuren_board import Liuren
from fatebridge.core.contracts.output_qimen_board import Qimen
from fatebridge.core.contracts.output_taiyi_board import Taiyi


class HeluoHexagram(PartialOutput):
    lines: list[int] | None = None
    name: str | None = None
    yuan: int | None = None
    low: str | None = None
    up: str | None = None


class HeluoChart(PartialOutput):
    cycleYear: int | None = None
    yuanCycle: str | None = None
    yangLingBasis: str | None = None
    yuantang_derivation: HeluoYuantangDerivation | None = None
    di: int | None = None
    diGua: str | None = None
    diNum: int | None = None
    gender: str | None = None
    hourZhi: str | None = None
    tian: int | None = None
    tianGua: str | None = None
    tianNum: int | None = None
    tianTop: bool | None = None
    yangGan: bool | None = None
    yangLing: bool | None = None
    yangMing: bool | None = None
    hou: HeluoHexagram | None = None
    xian: HeluoHexagram | None = None


class HeluoPeriod(PartialOutput):
    ageEnd: int | None = None
    ageStart: int | None = None
    gua: str | None = None
    lines: list[int] | None = None
    pos: int | None = None
    yang: bool | None = None
    yearStart: int | None = None
    years: int | None = None


class HeluoDayun(PartialOutput):
    all: list[HeluoPeriod] | None = None
    hou: list[HeluoPeriod] | None = None
    xian: list[HeluoPeriod] | None = None
    endAge: int | None = None
    xianEndAge: int | None = None


class LocalAngles(PartialOutput):
    ascendant: float | None = None
    midheaven: float | None = None


class LocalHouse(PartialOutput):
    id: str | None = None
    lon: float | None = None
    sign: str | None = None
    sign_zh: str | None = None


class LocalObject(PartialOutput):
    house: str | None = None
    ecliptic_house_position: float | None = None
    ecliptic_house_phase_degrees_ratio: str | None = Field(
        default=None,
        description="原生宫位模型的工作相位（有理数文本，现代度）；保留细微边界供反向分宫，不代表物理精度或唯一性获证",
    )
    id: str | None = None
    lon: float | None = None
    sign: str | None = None
    signlon: float | None = None


class LocalChart(PartialOutput):
    angles: LocalAngles | None = None
    houses: list[LocalHouse] | None = None
    objects: list[LocalObject] | None = None
    ok: bool | None = None


class LocalChartBundle(PartialOutput):
    chart: LocalChart | None = None
    params: Object | None = None


class SanshiSubresult(PartialOutput):
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    four_pillars: FourPillars | None = None
    liureng: Liuren | None = None


class QimenSubresult(SanshiSubresult):
    pan: Qimen | None = None


class TaiyiSubresult(SanshiSubresult):
    pan: Taiyi | None = None


class SanshiSubresults(PartialOutput):
    liureng_gods: SanshiSubresult | None = None
    qimen: QimenSubresult | None = None
    taiyi: TaiyiSubresult | None = None
