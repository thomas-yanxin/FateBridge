"""Request contracts for divination."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    ValidationInfo,
    field_validator,
    model_validator,
)

from fatebridge.core.heluo_months import DEFAULT_MONTH_ASSIGNMENT, MonthAssignmentMethod
from fatebridge.core.metaphysics.ren_gods import GuirenProfile
from fatebridge.core.numerology_inputs import (
    BIRTH_OFFSET_DESCRIPTION,
    NUMEROLOGY_DATE_DESCRIPTION,
    NUMEROLOGY_DEFAULT_TIMEZONE,
    NUMEROLOGY_TIME_DESCRIPTION,
    normalize_numerology_utc_offset,
    resolve_numerology_timezone,
)
from fatebridge.core.requests.base import _DeferredModel
from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.core.sukuyo_calendar_basis import SukuyoCalendarBasis
from fatebridge.core.sukuyo_lower import SukuyoActivityDetail, validate_activity_details
from fatebridge.utils.house_systems import OFFLINE_HOUSE_CODE_NOTE


class MeihuaAnalysisRequest(MeihuaInterpretationOptions):
    """Request model for time-seeded Mei Hua Yi Shu analysis."""

    analysis_year: int = Field(
        description="Gregorian analysis year; supported civil dates: 1900-01-01 to 2100-12-31"
    )
    analysis_month: int = Field(ge=1, le=12, description="Analysis month (1-12)")
    analysis_day: int = Field(ge=1, le=31, description="Analysis day (1-31)")
    analysis_hour: int = Field(ge=0, le=23, description="Analysis hour (0-23)")
    analysis_minute: Optional[StrictInt] = Field(
        default=None,
        ge=0,
        le=59,
        description="Confirmed civil minute (strict integer 0-59), when known. Omitted/null means unavailable; numerical00 is only the nominal calculation reference, not a claim that the event occurred on the hour. No rounding or measurement-error interval is inferred. Minute and second never add to the cast seed.",
    )
    analysis_second: Optional[StrictInt] = Field(
        default=None,
        ge=0,
        le=59,
        description="Optional civil second (0-59), only when known; preserves the instant for solar-term boundaries, never an additional cast seed. Omitted/null keeps the existing minute anchored at second 00. Input precision does not certify clock or ephemeris accuracy; leap-second label 60 is unsupported.",
    )
    analysis_timezone: Optional[str] = Field(
        default=None,
        description="Civil-clock timezone (IANA or UTC offset; defaults to Asia/Shanghai). Keep the named zone when using analysis_utc_offset to select a repeated clock. Nonexistent clocks remain invalid. A regional rule whose selected local time is unspecified cannot be treated as UTC; use a confirmed fixed offset as analysis_timezone when available.",
    )
    analysis_utc_offset: Optional[str] = Field(
        default=None,
        description="Optional explicit UTC offset, ±HH:MM or ±HH:MM:SS. Verified jointly with analysis_timezone at the supplied local clock; selects a fold without replacing the named calendar zone. Cannot rescue a DST gap or skipped date. Omit to keep rejecting ambiguous clocks. An offset cannot certify an unspecified regional time type; a confirmed fixed offset belongs in analysis_timezone.",
    )
    question: Optional[str] = Field(
        default=None, description="Question or topic for the divination context"
    )


class GuaLookupRequest(_DeferredModel):
    """Request model for trigram/hexagram lookup."""

    query: str = Field(description="Hexagram/trigram name or binary code")
    lookup_mode: str = Field(
        default="auto",
        description="Lookup mode: auto, hexagram, or trigram",
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class GuaMeiyiRequest(_DeferredModel):
    """Request model for batch Meiyi hexagram meanings."""

    name: List[str] = Field(description="Trigram or hexagram names/codes")
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class TongSheFaRequest(_DeferredModel):
    """Request model for tongshefa."""

    taiyin: Optional[str] = Field(default="巽", description="Taiyin trigram")
    taiyang: Optional[str] = Field(default="坤", description="Taiyang trigram")
    shaoyang: Optional[str] = Field(default="震", description="Shaoyang trigram")
    shaoyin: Optional[str] = Field(default="震", description="Shaoyin trigram")


class SixYaoLineRequest(_DeferredModel):
    """One six-yao line item."""

    value: StrictInt = Field(ge=0, le=1, description="0 for yin, 1 for yang")
    change: StrictBool = Field(default=False, description="Whether the line is moving")
    god: Optional[str] = Field(default=None, description="Optional six-god label")
    name: Optional[str] = Field(default=None, description="Optional line label")


class SixYaoRequest(_DeferredModel):
    """Request model for sixyao."""

    date: str = Field(description="Date string, e.g. 2028-04-06")
    time: str = Field(description="Time string, e.g. 09:33:00")
    zone: Optional[str] = Field(default="+08:00", description="Timezone spec")
    lat: Optional[str] = Field(default="31n13", description="Latitude text or decimal")
    lon: Optional[str] = Field(
        default="121e28", description="Longitude text or decimal"
    )
    gps_lat: Optional[float] = Field(default=None, description="GPS latitude")
    gps_lon: Optional[float] = Field(default=None, description="GPS longitude")
    question: Optional[str] = Field(default=None, description="Question or topic")
    focus_line: Optional[StrictInt] = Field(
        default=None,
        ge=1,
        le=6,
        description="调用方明确选定的用神爻位，初爻为1；默认取本爻，focus_kind可选变爻或已列伏神",
    )
    focus_kind: Optional[Literal["visible", "changed", "hidden", "month", "day"]] = (
        Field(
            default=None,
            description="明确取本爻visible、实际变爻changed、已列伏神hidden、月建month或日辰day；日月不带爻位，未指定时保留本变候选",
        )
    )
    focus_kinship: Optional[Literal["父母", "兄弟", "子孙", "妻财", "官鬼"]] = Field(
        default=None,
        description="明确选用的六亲；多现保留候选，与focus_line并用时须一致",
    )
    timing_days: StrictInt = Field(
        default=0,
        ge=0,
        le=60,
        description="按已明确的用爻列未来0至60个干支日的条件候选；0不展开，不是事件发生保证",
    )
    event_horizon: Optional[Literal["near", "long_term"]] = Field(
        default=None,
        description="调用方已明确问近事near或久远long_term时传入；用于原典进退条件，未给保持待定，不从timing_days推断",
    )
    gua_code: Optional[str] = Field(
        default=None,
        pattern=r"^[01]{6}$",
        description="Current hexagram code, initial line first",
    )
    changed_code: Optional[str] = Field(
        default=None,
        pattern=r"^[01]{6}$",
        description="Changed hexagram code, initial line first",
    )
    lines: List[SixYaoLineRequest] = Field(
        default_factory=list,
        max_length=6,
        description="Optional six lines, initial line first",
    )
    method: str = Field(
        default="auto",
        description=(
            "起卦方式：auto（默认，缺卦则按时刻时间起卦）/ coin（真·摇钱起卦，"
            "系统随机六掷）/ time（时间起卦）。提供 coins/lines/gua_code 时优先使用所提供的卦，重复输入必须一致。"
        ),
    )
    coins: Optional[List[Annotated[StrictInt, Field(ge=6, le=9)]]] = Field(
        default=None,
        min_length=6,
        max_length=6,
        description=(
            "摇钱起卦六掷之和（初爻→上爻），每掷为三枚铜钱之和 6/7/8/9"
            "（字面=2、背面=3）。提供则按真实摇出的铜钱结果装卦。"
        ),
    )
    seed: Optional[StrictInt] = Field(
        default=None,
        description="随机摇钱起卦的随机种子（method=coin 且未提供 coins 时），用于复现同一卦。",
    )

    @model_validator(mode="after")
    def complete_lines(self) -> "SixYaoRequest":
        if self.lines and len(self.lines) != 6:
            raise ValueError("六爻 lines 必须恰为 6 条，按初爻至上爻排列")
        if self.focus_kind in ("month", "day") and self.focus_line is not None:
            raise ValueError("日月取用不能同时指定爻位")
        if (
            self.focus_kind in ("visible", "changed", "hidden")
            and self.focus_line is None
            and self.focus_kinship is None
        ):
            raise ValueError("指定爻类取用还须提供focus_line或focus_kinship")
        if (
            self.timing_days
            and self.focus_line is None
            and self.focus_kinship is None
            and self.focus_kind is None
        ):
            raise ValueError("展开日级候选需要先明确focus_line或focus_kinship")
        return self


class SuZhanRequest(_DeferredModel):
    """Request model for suzhan."""

    calendar_basis: SukuyoCalendarBasis = Field(
        default="chinese_hko_utc08",
        description="宿主历法独立于出生时区和配宿档案。默认现代中国农历UTC+08；japanese_hutime_1002_1_utc09用1872-02-09至2031-01-22的HuTime逐日参考、固定UTC+09；2015起为出版方参考推算，非历史地方时或逐年神宫原刊验收，范围外不回退其他历法。japanese_naoj_historical_utc09为公元0001-01-01至1872-12-31的NAOJ历史月朔参考、固定UTC+09；早期纪年属重建，改历末月仅两天，保留跨出版方异日，非历史地方时或全部颁历验收。",
    )

    textual_pada: Optional[StrictInt] = Field(
        default=None,
        ge=1,
        le=4,
        description="仅按本次历日宿名查T1299分足表的显式第1..4足条件；非已排得出生足位，不能按钟时或现代月亮补造；省略保留四足候选",
    )

    calendar_profile: Literal["t1299_fullmoon27", "hinoo_t1299_host27"] = Field(
        default="t1299_fullmoon27",
        description="历日27宿档案：默认T1299下卷望日逆顺/生日加十三法；hinoo_t1299_host27另用T2465闰月复用及小月分宿研究规则，仍非历史旧历复原",
    )
    calendar_day_part: Optional[Literal["first_half", "second_half"]] = Field(
        default=None,
        description="仅Hinoo档案：已确定的原典日序前/后半；不由出生钟时自动推断，缺项保留候选",
    )
    activity_details: List[SukuyoActivityDetail] = Field(
        default_factory=list,
        description="已确认的事项细节，须与activity对应；不从出生资料、GPS或目的地猜测。本人启程personal_departure不等于因私出行private_journey；王公百官行旅身份royal_or_official_traveler不由出差或使节任务推断。明确结交交友forming_friendship（不限首次相识）与聚会social_gathering分别核对，不互相代填。远行人入宅long_distance_traveler_entering_residence不自动当启程；出家人请教法要monastic_dharma_request需明确身份与动作。借贷、买卖、远近、方向及技艺等条件只在给定时匹配；空列表保留条件文，未列条件不等于已排除。",
    )
    mansion_method: Literal["equatorial_research28", "legacy_equal28"] = Field(
        default="equatorial_research28",
        description="天文28宿：默认采用当日视赤经和已声明现代距星的不等宽研究宿界（七曜）；legacy_equal28仅作旧版等分黄道示意；均不决定农历本命宿",
    )
    activity: Optional[
        Literal[
            "social",
            "marriage",
            "travel",
            "relocation",
            "commerce",
            "study",
            "clothing",
        ]
    ] = Field(
        default=None,
        description="按事项核对T1299三九、宿性、逐宿、七曜、日名及专章条文；clothing须区分裁缝tailoring_garments、制作making_garments、修理repairing_garments、穿着wearing_garments和穿新衣wearing_new_garments。royal_wearer仅为明确王者身份，不由穿礼服推断；衣事不等于买衣。其他事项亦读取已确认activity_details，保留冲突、版本异文及钟时缺项",
    )

    leap_month_policy: Literal["unresolved", "repeat_month"] = Field(
        default="unresolved",
        description="闰月配宿默认保留候选；repeat_month显式沿用同名月",
    )
    natal_mansion: Optional[str] = Field(
        default=None,
        description="已核定的农历二十七宿本命宿（不含牛）；提供则计算本命六宫宿位置及命宿到历日宿的三九关系；七曜运行犯宿另未计算，不从黄经星图提取本命宿",
    )
    date: str = Field(
        description="公历日期；历日宿按显式calendar_basis选择宿主历法与参考日界，默认现代中国农历UTC+08"
    )
    time: Optional[str] = Field(
        default=None,
        description="已确认的当地钟时；未知时省略或null，保留历法日期／半日候选，不计算星图、宫位或瞬时天文宿位，不补00:00或示例钟时。空字符串无效。",
    )
    zone: Optional[str] = Field(default="+08:00", description="Timezone spec")
    lat: Optional[str] = Field(default="31n13", description="Latitude text or decimal")
    lon: Optional[str] = Field(
        default="121e28", description="Longitude text or decimal"
    )
    gps_lat: Optional[float] = Field(default=None, description="GPS latitude")
    gps_lon: Optional[float] = Field(default=None, description="GPS longitude")
    szchart: int = Field(
        default=0, description="宿占盘模式开关（透传至宿曜引擎；默认 0）"
    )
    szshape: int = Field(
        default=0, description="宿占盘形态开关（透传至宿曜引擎；默认 0）"
    )
    house_start_mode: int = Field(
        default=1,
        description="宫位起始模式（透传至宿曜引擎；默认 1）",
    )
    doubing_su28: bool = Field(
        default=True,
        description="是否按mansion_method标注天文28宿；不用于农历本命宿；默认仅七个物理七曜有现代研究宿位",
    )
    hsys: int = Field(
        default=8,
        ge=0,
        le=8,
        description="Offline house system selector; standard suzhan supports 0..8 with the same FateBridge local house semantics as core chart"
        + OFFLINE_HOUSE_CODE_NOTE,
    )
    zodiacal: int = Field(
        default=0,
        description="Offline zodiac selector; standard suzhan supports 0=tropical and 1=sidereal(Lahiri-like)",
    )

    @model_validator(mode="after")
    def day_part_requires_hinoo(self) -> "SuZhanRequest":
        if (
            self.calendar_day_part is not None
            and self.calendar_profile != "hinoo_t1299_host27"
        ):
            raise ValueError("原典日序半日只适用于明确选择的Hinoo研究档案")
        validate_activity_details(self.activity, self.activity_details)
        return self


class CanpingRequest(_DeferredModel):
    """Request model for canping (邵子参评数 / 金锁银匙)."""

    date: str = Field(description=NUMEROLOGY_DATE_DESCRIPTION)
    time: str = Field(description=NUMEROLOGY_TIME_DESCRIPTION)
    zone: Optional[str] = Field(
        default=NUMEROLOGY_DEFAULT_TIMEZONE,
        description="IANA zone or UTC offset; omitted/null means fixed +08:00, not historical Asia/Shanghai. Blank/invalid zones and nonexistent clocks are rejected. Repeated clocks require a confirmed birth_utc_offset; the IANA zone remains in use for later boundaries.",
    )
    birth_utc_offset: Optional[str] = Field(
        default=None, description=BIRTH_OFFSET_DESCRIPTION
    )
    lat: Optional[str] = Field(
        default=None, description="Latitude text or decimal (optional)"
    )
    lon: Optional[str] = Field(
        default=None,
        description="Longitude text or decimal; required when true solar time is on",
    )
    gps_lat: Optional[float] = Field(default=None, description="GPS latitude")
    gps_lon: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
        strict=True,
        description="Explicit numeric GPS longitude; preferred over lon; zero is valid",
    )
    gender: str = Field(
        description=(
            "需明确男/女：选择男女条文及附子平法配运方向；接受male/female，不默认性别。"
        ),
    )
    method: Literal["gu", "ming"] = Field(
        default="gu",
        description="取法: gu（默认，卷六金锁银匙用八字日支、不用月令）；ming 为月支反向变法，非该段原典算法",
    )
    dayun_method: Literal[
        "bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"
    ] = Field(
        default="bazi_appendix_v1",
        description="配运政策：默认卷七附子平月柱顺逆、三日折岁借除整日；continuous为现代连续折算；legacy仅复核旧命宫顺排一岁起运，未获原典认证。不是河洛六九年大限。",
    )
    analysis_datetime: Optional[str] = Field(
        default=None,
        description="可选带时区ISO时刻，查询实际交运和立春年界后的当段参评数；无默认当前时刻，legacy方法不支持精确时刻查询。",
    )
    use_true_solar_time: bool = Field(
        default=True,
        description="Apply true solar time correction (needs lon); default on — 数算 derives from the BaZi pillars",
    )

    @field_validator("gender")
    @classmethod
    def known_canping_gender(cls, value: str) -> str:
        from fatebridge.utils.birth_input import normalize_gender

        gender = normalize_gender(value)
        if gender not in {"男", "女"}:
            raise ValueError("参评男女条文及配运需要明确男/女，不能默认性别。")
        return gender

    @field_validator("time", mode="before")
    @classmethod
    def explicit_canping_clock(cls, value: object) -> str:
        from fatebridge.core.numerology_clock_input import preserve_birth_clock_text

        return preserve_birth_clock_text(value)

    @field_validator("birth_utc_offset", mode="before")
    @classmethod
    def confirmed_birth_offset(cls, value: object) -> Optional[str]:
        return normalize_numerology_utc_offset(value)

    @field_validator("zone", mode="before")
    @classmethod
    def explicit_canping_zone(cls, value: object) -> str:
        return resolve_numerology_timezone(value)

    @field_validator("analysis_datetime")
    @classmethod
    def aware_canping_query(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            from fatebridge.utils.civil_clock import parse_iso_datetime

            at = parse_iso_datetime(value.replace("Z", "+00:00"))
            if at.tzinfo is None or at.utcoffset() is None:
                raise ValueError("analysis_datetime须为带时区的ISO时刻。")
        return value

    @model_validator(mode="after")
    def canping_luck_query_policy(self) -> "CanpingRequest":
        from fatebridge.core.numerology_inputs import resolve_numerology_longitude

        resolve_numerology_longitude(self.lon, self.gps_lon, self.use_true_solar_time)
        if (
            self.dayun_method == "legacy_minggong_v1"
            and self.analysis_datetime is not None
        ):
            raise ValueError("legacy方法没有已核实的日期映射，不能查询精确时刻。")
        return self


class HeluoRequest(_DeferredModel):
    """Request model for heluo (河洛理数)."""

    month_assignment_method: MonthAssignmentMethod = Field(
        default=DEFAULT_MONTH_ASSIGNMENT,
        description="卦属月原文位置：intro_preferred_v1默认优先卦条63项，无妄缺号采用卷首8月；volume_one_table_v1采用卷首64项。晋、节、睽、震、井有底本内异号，输出保留双方；只影响卦月匹配，不解决月界或综合得时。",
    )

    date: str = Field(description=NUMEROLOGY_DATE_DESCRIPTION)
    time: str = Field(description=NUMEROLOGY_TIME_DESCRIPTION)
    zone: Optional[str] = Field(
        default=NUMEROLOGY_DEFAULT_TIMEZONE,
        description="IANA zone or UTC offset; omitted/null means fixed +08:00, not historical Asia/Shanghai. Blank/invalid zones and nonexistent clocks are rejected. Repeated clocks require a confirmed birth_utc_offset; the IANA zone remains in use for later boundaries.",
    )
    birth_utc_offset: Optional[str] = Field(
        default=None, description=BIRTH_OFFSET_DESCRIPTION
    )
    lat: Optional[str] = Field(
        default=None, description="Latitude text or decimal (optional)"
    )
    lon: Optional[str] = Field(
        default=None,
        description="Longitude text or decimal; required when true solar time is on",
    )
    gps_lat: Optional[float] = Field(default=None, description="GPS latitude")
    gps_lon: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
        strict=True,
        description="Explicit numeric GPS longitude; preferred over lon; zero is valid",
    )
    gender: str = Field(
        description=(
            "性别 男/女 — 影响起命相盪与元堂推导。接受 男/女、male/female 等写法；"
            "必须明确提供，不默认性别。"
        ),
    )
    use_true_solar_time: bool = Field(
        default=True,
        description="Apply true solar time correction (needs lon); default on — 数算 derives from the BaZi pillars",
    )
    analysis_year: Optional[int] = Field(
        default=None,
        strict=True,
        description="可选：选择干支年对应的公历年标签，如2028；不是公历整年或精确年界区间，不填时不自动选当前年",
    )
    month_index: Optional[int] = Field(
        default=None,
        strict=True,
        ge=1,
        le=12,
        description="原典月卦序号1..12，须传analysis_year；不是公历月份，未确定实际日期映射",
    )
    day_index: Optional[int] = Field(
        default=None,
        strict=True,
        ge=1,
        le=30,
        description="原典三十日定式序号1..30，须传month_index；不是公历或农历生日，不提供精确应期",
    )

    @field_validator("gender")
    @classmethod
    def known_heluo_gender(cls, value: str) -> str:
        from fatebridge.utils.birth_input import normalize_gender

        gender = normalize_gender(value)
        if gender not in {"男", "女"}:
            raise ValueError("河洛相荡、寄宫和元堂需要明确男/女，不能默认性别。")
        return gender

    @field_validator("time", mode="before")
    @classmethod
    def explicit_heluo_clock(cls, value: object) -> str:
        from fatebridge.core.numerology_clock_input import preserve_birth_clock_text

        return preserve_birth_clock_text(value)

    @field_validator("birth_utc_offset", mode="before")
    @classmethod
    def confirmed_birth_offset(cls, value: object) -> Optional[str]:
        return normalize_numerology_utc_offset(value)

    @field_validator("zone", mode="before")
    @classmethod
    def explicit_heluo_zone(cls, value: object) -> str:
        return resolve_numerology_timezone(value)

    @model_validator(mode="after")
    def require_timing_parent(self) -> "HeluoRequest":
        from fatebridge.core.numerology_inputs import resolve_numerology_longitude

        resolve_numerology_longitude(self.lon, self.gps_lon, self.use_true_solar_time)
        if self.month_index is not None and self.analysis_year is None:
            raise ValueError("month_index需要analysis_year年标签。")
        if self.day_index is not None and self.month_index is None:
            raise ValueError("day_index需要month_index月序号。")
        return self


class OtherBuRequest(_DeferredModel):
    """Three actual dice faces, optionally accompanied by a separate sky chart."""

    date: Optional[str] = Field(
        default=None,
        description="Optional Gregorian date for a separate sky chart; provide time/zone/coordinates too",
    )
    time: Optional[str] = Field(
        default=None, description="Optional civil time for a separate sky chart"
    )
    zone: Optional[str] = Field(
        default=None,
        description="Explicit IANA timezone or UTC offset for the separate sky chart",
    )
    lat: Optional[str] = Field(
        default=None, description="Latitude text or decimal; no assumed location"
    )
    lon: Optional[str] = Field(
        default=None, description="Longitude text or decimal; no assumed location"
    )
    gps_lat: Optional[float] = Field(default=None, description="GPS latitude")
    gps_lon: Optional[float] = Field(default=None, description="GPS longitude")
    tradition: bool = Field(
        default=False,
        description="Exclude outer planets only from the separate sky chart; never alter the rolled face",
    )
    sign: str = Field(
        description="Actual dice sign: English name, Chinese name or zodiac glyph; never guessed"
    )
    house: int = Field(
        ge=0,
        le=11,
        strict=True,
        description="Actual dice house INDEX (0-11): printed house N must be submitted as N-1",
    )
    planet: str = Field(
        description="Actual face: Sun/Moon/Mercury/Venus/Mars/Jupiter/Saturn/Uranus/Neptune/Pluto/NorthNode/SouthNode; Chinese names and glyphs accepted"
    )
    hsys: int = Field(
        default=8,
        ge=0,
        le=8,
        strict=True,
        description="House system 0..8 for the separate sky chart; does not change the symbolic wheel",
    )
    zodiacal: int = Field(
        default=0,
        ge=0,
        le=1,
        strict=True,
        description="Separate sky chart only: 0=tropical, 1=sidereal(Lahiri); never reinterprets a dice sign",
    )
    question: Optional[str] = Field(default=None, description="Question or topic")
    fortune_method: Literal["sect_reversing", "ptolemy_iii10"] = Field(
        default="sect_reversing",
        description="Separate sky Fortune only: sect_reversing uses day/night reversal; ptolemy_iii10 follows Robbins 1940 III.10 (ASC+Moon-Sun both day and night). Does not alter dice interpretation.",
    )

    @field_validator("gps_lat", "gps_lon", mode="before")
    @classmethod
    def actual_gps_coordinate(cls, value: Any, info: ValidationInfo) -> Optional[float]:
        from fatebridge.utils.coordinates import parse_geo_coordinate

        if value is None:
            return None
        parsed = parse_geo_coordinate(
            value, axis="latitude" if info.field_name == "gps_lat" else "longitude"
        )
        if parsed is None:
            raise ValueError("GPS坐标不可为空白")
        return parsed

    @field_validator("sign")
    @classmethod
    def actual_sign(cls, value: str) -> str:
        from fatebridge.core.astrodice import normalize_sign

        return normalize_sign(value)

    @field_validator("planet")
    @classmethod
    def actual_planet(cls, value: str) -> str:
        from fatebridge.core.astrodice import normalize_planet

        return normalize_planet(value)

    @model_validator(mode="after")
    def explicit_sky_context(self) -> "OtherBuRequest":
        from fatebridge.core.astrodice import validate_context

        validate_context(
            date=self.date,
            time=self.time,
            zone=self.zone,
            lat=self.lat,
            lon=self.lon,
            gps_lat=self.gps_lat,
            gps_lon=self.gps_lon,
        )
        return self


class SanShiUnitedRequest(_DeferredModel):
    """Request model for sanshiunited."""

    date: str = Field(
        description="推算公历日期，例如2028-04-06；历史儒略历标签须先明确转换，不自动切换历制。"
    )
    time: str = Field(description="Time string, e.g. 09:33:00")
    zone: Optional[str] = Field(default="+08:00", description="Timezone spec")
    lat: Optional[str] = Field(default="31n13", description="Latitude text or decimal")
    lon: Optional[str] = Field(
        default="121e28", description="Longitude text or decimal"
    )
    gps_lat: Optional[float] = Field(default=None, description="GPS latitude")
    gps_lon: Optional[float] = Field(default=None, description="GPS longitude")
    qimen_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="奇门：ju_method=zhirun（置闰）/chaibu（拆补）；god_profile=yanyi_text（默认卷三正文）/yanyi_diagrams（卷四圆图）；season_profile=yanyi_vol1_verse（默认卷一赋）/yanyi_vol3_table/yanyi_vol3_prose；仅支持转盘layout=direct和零平移",
    )
    taiyi_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="太乙calculation_mode=year/month/day/hour，默认year；仅year可设year_profile=jinjing_year_historical_table_v1选381—385晋历主表，或jinjing_year_qiliang_table_v1选501—505齐梁史历表并保留502年闰标分歧；范围外拒绝，其他两术古历不因而认证；默认年计仍为通用现代农历。仅month可设month_profile=jinjing_month_jie_360_v1（默认金镜）/key_month_tianzheng_jie_v1（金钥匙天地二正，现代节月适配，门数分歧及三门未知保留）；day为金钥匙冬至前甲子积日、所选钟面零时换日，附十精及异数；仅hour可设hour_profile=jinjing_hour_solstice_v1（默认现代至点置一）或key_hour_winter_jiazi_v1（金钥匙完整积时/时支合神/四门，三门主体未决）。仅兼容accNum/acc_num=0；年/月可兼容顺布，日/时计不接受rotation覆盖。日计古历日期仍未复原，不按吉凶择法。",
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )
    liureng_yue: Optional[str] = Field(
        default=None,
        description="Optional liureng month-general override",
    )
    liureng_is_diurnal: Optional[bool] = Field(
        default=None,
        description="Optional liureng day/night override",
    )
    liureng_guiren_profile: GuirenProfile = Field(
        default="liuren_common_v1",
        description="六壬贵人本位：liuren_common_v1（默认通行表）或tanyuan_xieji_v1（探原协纪表）。与金镜明钞／四库当时法的本位逐版对照，不自动择优；昼夜边界、四维寄支及完整合参断法另待验收。",
    )
    use_true_solar_time: bool = Field(
        default=True,
        description="Enable local true solar time correction before sanshi aggregation (default on — 式占 keys off the apparent-solar 时辰)",
    )
