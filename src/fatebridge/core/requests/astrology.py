"""Request contracts for astrology."""

from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from fatebridge.core.requests.birth import AstroBirthRequest
from fatebridge.core.requests.western_policy import WesternEphemerisRequest
from fatebridge.utils.house_systems import OFFLINE_HOUSE_CODE_NOTE

GuolaoSeasonalAnchorPolicy = Literal[
    "term_instants",
    "source_solar_days_winter_exclusive",
    "source_solar_days_winter_inclusive",
]


class AstroChartRequest(AstroBirthRequest, WesternEphemerisRequest):
    """Request model for offline astrology chart generation."""

    gender: Optional[str] = Field(
        default="未知",
        description=(
            "性别（可选，仅用于结果标识；西方星盘计算不使用性别）。接受此字段是为了让"
            "同一套出生信息可以原样喂给八字/紫微/星盘等工具，避免批量调用时'有的工具收、"
            "有的不收'造成的反复试错。"
        ),
    )
    birth_timezone: Optional[str] = Field(  # type: ignore[assignment]
        default=None,
        description=(
            "Birth timezone (IANA name or UTC offset). May be resolved from a "
            "supported birth_place; Western charts reject an unresolved civil "
            "timezone. Coordinates cannot establish the recorded zone. Explicit "
            "UTC is valid; never infer a historical basis by fitting a chart. "
            "Indian charts also require a resolved civil timezone."
        ),
    )
    birth_longitude: Optional[float] = Field(  # type: ignore[assignment]
        default=None,
        ge=-180,
        le=180,
        description=(
            "Birth longitude. Optional for core chart endpoints when FateBridge can "
            "infer it from a supported birth_place."
        ),
    )
    birth_latitude: Optional[float] = Field(  # type: ignore[assignment]
        default=None,
        ge=-90,
        le=90,
        description=(
            "Birth latitude. Optional for core chart endpoints when FateBridge can "
            "infer it from a supported birth_place."
        ),
    )
    hsys: Optional[int] = Field(
        default=None,
        ge=0,
        le=8,
        description=(
            "Optional offline house system override; if omitted, FateBridge keeps each "
            "chart variant's historical default. Explicit values currently support "
            "0=whole_sign, 1=Alcabitus, 2=Regiomontanus, 3=Placidus, 4=Koch, "
            "5=Vehlow Equal, 6=Polich Page, 7=Sripati, 8=equal_mc"
        )
        + OFFLINE_HOUSE_CODE_NOTE,
    )
    zodiacal: Optional[int] = Field(
        default=None,
        description=(
            "Optional offline zodiac override; if omitted, FateBridge keeps each "
            "chart variant's historical default. Explicit values currently support "
            "0=tropical and 1=sidereal(Lahiri-like)"
        ),
    )
    use_true_solar_time: bool = Field(
        default=False,
        description=(
            "Rebase the birth clock onto true solar time (longitude + equation of "
            "time). Default OFF: western astrology conventionally casts on the "
            "recorded civil (zone) clock time. Set true to align the western chart "
            "with the BaZi engine's apparent-solar instant."
            " Guolao and Indian charts preserve the recorded civil instant and report the solar clock separately."
        ),
    )


class AstroGuolaoRequest(AstroChartRequest):
    """Explicit target instant for the partial Guolao temporal research layer."""

    def uses_western_ephemeris_policy(self) -> bool:
        return False

    ephemeris_policy: Literal["auto", "require_data_files"] = Field(
        default="auto",
        description="Guolao retains its existing observed source rules; the Western require_data_files request policy is not implemented for this variant.",
    )

    birth_timezone: Optional[str] = Field(
        default=None,
        description="For civil input: IANA name or explicit UTC offset; omit only if birth_place resolves a timezone. Unresolved missing timezones are rejected and are not defaulted to UTC. For explicit LMT/LAT input this field must be omitted: a solar label is not a civil timezone. Converted UTC labels and native TT/UT1 are computation references, not inferred historical zones; no surrogate datetime is created for second60 or out-of-range UTC labels.",
    )
    birth_clock_basis: Literal["civil", "local_mean_solar", "local_apparent_solar"] = (
        Field(
            default="civil",
            description="Confirmed basis of the supplied birth label. Civil retains its timezone policy. LMT/LAT use longitude and the shared modeled UT1/TT inverse; omit birth_timezone. LMT uses its recorded label for the nominal hour unless use_true_solar_time=true selects the same natal Sun's apparent hour without changing the epoch. LAT already supplies an apparent label; either flag keeps its nominal input hour and applies no second correction. Do not infer an unknown historical clock basis. When UTC is outside datetime range, second60, or lacks a unique label, Guolao retains native TT/UT1 without a surrogate civil instant. Solar-day numerical ambiguity, unavailable month calendars, source coverage and native ordering ties remain explicit limits; no classical clock calibration or prediction certification.",
        )
    )

    birth_second: int = Field(
        default=0,
        ge=0,
        le=59,
        description="Recorded birth second, if known. Omitted seconds use the start of the supplied minute; this does not certify exact recording precision. Leap-second labels are not represented.",
    )
    birth_microsecond: int = Field(
        default=0,
        ge=0,
        le=999999,
        description="Explicit fraction of the recorded birth second. Preserved in the physical instant and solar-hour calculation; datetime resolution does not certify source-clock or astronomical accuracy.",
    )

    analysis_datetime: Optional[AwareDatetime] = Field(
        default=None,
        description="Optional ISO target instant with timezone offset, at or after recorded birth. Returns source-ordinal small-limit palace with declared LiChun year policy and actual geocentric target seven bodies / four-extra models. Omit for natal only; no implicit today, full classical temporal judgement or event probability.",
    )
    guolao_month_basis: Optional[Literal["jie_month", "chinese_lunar_utc8"]] = Field(
        default=None,
        description="Optional Guolao monthly-limit research policy; requires analysis_datetime. jie_month uses calculated Jie boundaries with Yin=month 1; chinese_lunar_utc8 uses regular Chinese lunar month numbers on UTC+08 civil dates and leaves intercalary birth/target months unassigned. Neither mapping is certified by the cited edition. The annual small limit keeps its declared LiChun year policy. Omit to leave the monthly layer unrequested.",
    )

    guolao_seasonal_anchor_policy: Optional[GuolaoSeasonalAnchorPolicy] = Field(
        default=None,
        description="Optional Guolao anchor policy. term_instants preserves v7. source_solar_days_winter_exclusive/inclusive require use_true_solar_time=true or an explicit LAT input: use the same Sun/UT1 apparent-solar day, include the whole Major Cold, summer-solstice and Minor Heat days, and exclude/include the winter-solstice day. These explicit v8 hypotheses do not adjudicate historical day boundaries or predictive validity; numerical ambiguity and model changes error without fallback.",
    )

    @model_validator(mode="after")
    def _month_limit_requires_target(self) -> "AstroGuolaoRequest":
        if self.ephemeris_policy != "auto":
            raise ValueError("Western ephemeris_policy is not implemented for Guolao")
        if self.birth_clock_basis != "civil" and self.birth_timezone is not None:
            raise ValueError("Explicit solar birth labels must omit birth_timezone")
        if self.guolao_month_basis is not None and self.analysis_datetime is None:
            raise ValueError("guolao_month_basis requires analysis_datetime")
        if self.guolao_seasonal_anchor_policy in {
            "source_solar_days_winter_exclusive",
            "source_solar_days_winter_inclusive",
        } and not (
            self.use_true_solar_time or self.birth_clock_basis == "local_apparent_solar"
        ):
            raise ValueError(
                "Solar-day anchors require use_true_solar_time=true or explicit LAT input"
            )
        return self


class AstroSpecialtyRequest(AstroChartRequest):
    """Germany and equal13 charts with explicitly confirmed time uncertainty."""

    birth_second: int = Field(
        default=0,
        ge=0,
        le=59,
        description="Recorded birth second (0..59), for Germany/equal13 charts. Omission represents the start of the supplied minute, not proof of second-level birth-time accuracy. Preserve the user's stated precision and uncertainty; do not infer missing seconds from outcomes.",
    )

    birth_clock_basis: Literal["civil", "local_mean_solar", "local_apparent_solar"] = (
        Field(
            default="civil",
            description="Basis of the supplied birth clock, not a display preference. civil uses birth_timezone. Explicit local_mean_solar/LMT or local_apparent_solar/LAT uses longitude and modeled UT1/TT; omit birth_timezone and keep use_true_solar_time=false to avoid applying another correction. Never infer the basis of an ambiguous historical record by fitting a chart.",
        )
    )

    birth_time_uncertainty_minutes: Optional[float] = Field(
        default=None,
        ge=0,
        le=120,
        allow_inf_nan=False,
        description="User-confirmed +/- minutes around the recorded birth instant. None means unknown, not exact. Recalculates factors and the published source pattern / equal13 assignments on a UTC grid no wider than 30 seconds; samples are not a continuous-interval proof or probabilities.",
    )

    @model_validator(mode="after")
    def _solar_birth_clock_scope(self) -> "AstroSpecialtyRequest":
        if self.birth_clock_basis != "civil" and (
            self.birth_timezone is not None or self.use_true_solar_time
        ):
            raise ValueError(
                "Local solar birth clocks require birth_timezone omitted and use_true_solar_time=false"
            )
        return self


class AstroGermanyRequest(AstroSpecialtyRequest):
    """Optional target instant enables the explicit true-solar-arc layer."""

    analysis_datetime: Optional[AwareDatetime] = Field(
        default=None,
        description="Optional ISO target instant with timezone offset for true-solar-arc biwheel geometry and the explicitly named Witte-1924 ecliptic day-meridian equation. Uses a 365.25-day Julian symbolic year key, within 0..150 key years after effective birth. Omit for natal only. Symbolic directions/meridians are not physical target positions or event-success probabilities.",
    )


class AstroRelativePartyRequest(AstroBirthRequest):
    """One side of a relative/synastry request."""

    gender: Optional[str] = Field(
        default="未知",
        description="Shared subject label; not used in western chart calculation",
    )
    use_true_solar_time: bool = Field(
        default=False,
        description="Use apparent solar time for this party; defaults to civil time",
    )

    # AstroBirthRequest defaults birth_timezone to "UTC", which silently treats
    # an eastern wall-clock time as UTC and rotates the chart. Mirror the core
    # AstroChartRequest fix: default to None so the engine infers the zone from
    # birth_place and only falls back to UTC when no place is recognized.
    birth_timezone: Optional[str] = Field(  # type: ignore[assignment]
        default=None,
        description=(
            "Birth timezone (IANA name or UTC offset). Optional: when omitted, "
            "FateBridge may resolve it from a supported birth_place; otherwise "
            "the civil timezone is required. Coordinates alone are insufficient."
        ),
    )


class AstroRelativeRequest(WesternEphemerisRequest):
    """Request model for relative / synastry chart generation."""

    inner: AstroRelativePartyRequest
    outer: AstroRelativePartyRequest
    davison_variant: Literal["uncorrected", "corrected", "spherical"] = Field(
        default="uncorrected",
        description="TimeSpace/Marks: uncorrected UT1 time midpoint with dateline-aware coordinate mean; corrected aligns the tropical MC meridian axis; spherical uses the shortest great-circle midpoint. Nondefault variants require TimeSpace or Marks.",
    )
    relative_mode: Optional[Union[str, int]] = Field(
        default=None,
        description=(
            "Relative mode: 0/Comp=compare, 1/Composite=composite, "
            "2/Synastry=influence, 3/TimeSpace=timespace, 4/Marks=marks. "
            "Synastry/synastry both select the influence chart pair."
        ),
    )
    hsys: int = Field(
        default=3,
        ge=0,
        le=8,
        description="House system identifier (0..8 via local Swiss house cusps). "
        "Defaults to Placidus (3) to match the natal chart so a person's natal "
        "and relative charts share one house system." + OFFLINE_HOUSE_CODE_NOTE,
    )
    zodiacal: int = Field(
        default=0,
        description="Zodiac selector; offline mode currently supports 0=tropical and 1=sidereal(Lahiri-like) only",
    )
    relationship_focus: Optional[str] = Field(
        default=None,
        description=(
            "Optional relationship intent lens: marriage/婚姻 (emphasises 7th "
            "house + Sun/Moon/Venus/Saturn) or romance/恋爱 (emphasises 5th "
            "house + Sun/Moon/Venus/Mars). Adds a focus block + intent-filtered "
            "synastry aspects without changing computed aspects; default/unset "
            "is general (no filtering)."
        ),
    )


class AstroIndiaRequest(AstroChartRequest):
    """Lahiri Parashari subset; legacy zodiac/house overrides remain explicit."""

    def uses_western_ephemeris_policy(self) -> bool:
        return False

    birth_timezone: Optional[str] = Field(
        default=None,
        description="Civil birth timezone: explicit IANA name or UTC offset, or supported unambiguous birth_place inference. Unresolved civil timezones are rejected before sky calculations; coordinates, analysis_timezone and a solar-display request cannot establish the recorded zone. Explicit UTC is valid. Explicit LMT/LAT input requires this field omitted and a confirmed noncivil birth_clock_basis.",
    )

    birth_second: int = Field(
        default=0,
        ge=0,
        le=59,
        description="Recorded second, if known; omitted uses the beginning of the minute, not a claim of exact recording precision. Leap-second labels are not represented.",
    )
    birth_microsecond: int = Field(
        default=0,
        ge=0,
        le=999999,
        description="Numerical fraction of the supplied second, including explicitly converted clocks; does not certify source clock precision.",
    )
    birth_clock_basis: Literal["civil", "local_mean_solar", "local_apparent_solar"] = (
        Field(
            default="civil",
            description="Basis explicitly identified in the birth record. LMT/LAT requires birth_timezone omitted and use_true_solar_time=false; east-positive longitude and shared TT/UT1 convert it to an instant. Never infer an unknown clock basis by fitting the chart or outcomes.",
        )
    )

    use_true_solar_time: bool = Field(
        default=False,
        description="Report an apparent-solar wall-clock label separately. Recorded civil birth time and its physical ephemeris instant are preserved with either setting; this option cannot select a different birth date, dasha start or mean-model window. A known historical LAT/LMT record is not a civil input and must not be guessed with this switch.",
    )

    node_mode: Literal["mean", "true"] = Field(
        default="mean", description="Rahu: mean or true lunar node; Ketu is opposite."
    )
    ephemeris_policy: Literal["auto", "require_data_files"] = Field(
        default="auto",
        description="auto reports actual Swiss/Moshier provenance; require_data_files rejects analytical fallback for physical coordinates, sensitivity/rise-set samples and every Sun call resolving LAT clocks and their interval endpoints. Does not certify empirical prediction accuracy.",
    )
    saptavargaja_profile: Literal["santhanam_27", "raman_30"] = Field(
        default="santhanam_27",
        description="Saptavargaja coefficients and moolatrikona scope: Santhanam27 literal seven-sign reading or Raman30 D1-only exception. Changes this component only; Drekkana is independently selected by drekkana_profile. Neither certifies full Shadbala or predictive validity.",
    )
    drekkana_profile: Literal["santhanam_27_6", "raman_36"] = Field(
        default="santhanam_27_6",
        description="D1 decanate positional strength, independently of Saptavargaja: Santhanam27.6 gives Moon/Venus the middle decanate, Mercury/Saturn the last; Raman36 reverses them. Both use15 Virupa. Raman's detailed section36 and Example12 are selected explicitly; its conflicting summary60 remains unresolved. Not D3 chart longitude or whole-book acceptance.",
    )
    cheshta_model: Literal["unadjudicated", "simon1994_j2000"] = Field(
        default="unadjudicated",
        description="Five-star motional mean model: default keeps missing values; simon1994_j2000 explicitly selects modern secular means and separate geometric J2000 true positions, admitted1900-2050 TT only. Not Raman1900 tables, complete Shadbala or real-world predictive evidence. Sun/Moon rules remain separate.",
    )
    divisions: List[Literal[2, 3, 7, 9, 10, 12, 30]] = Field(
        default=[9, 10],
        max_length=7,
        description="Parashari charts to include: D2 traditional Sun/Moon Hora, D3, D7, D9, D10, D12, D30 unequal sign assignments only (no invented D30 longitude). Default [9,10]; D1 always included, [] requests D1 only.",
    )
    birth_time_uncertainty_minutes: Optional[float] = Field(
        default=None,
        ge=0,
        le=120,
        allow_inf_nan=False,
        description="User-confirmed +/- minutes. Civil input uses elapsed minutes around its resolved instant; LMT/LAT uses a recorded solar-wall interval whose endpoints are converted first. None means unknown, not exact. A physical UTC grid of at most30 seconds includes endpoints and nominal instant.",
    )

    @model_validator(mode="after")
    def _distinct_divisions(self) -> "AstroIndiaRequest":
        if len(self.divisions) != len(set(self.divisions)):
            raise ValueError("divisions must not contain duplicates")
        return self

    @model_validator(mode="after")
    def _solar_input_exclusions(self) -> "AstroIndiaRequest":
        if self.birth_clock_basis != "civil" and (
            self.birth_timezone is not None or self.use_true_solar_time
        ):
            raise ValueError(
                "Local solar birth clocks require birth_timezone omitted and use_true_solar_time=false"
            )
        return self


class AstroVimshottariRequest(AstroIndiaRequest):
    """Moon-nakshatra Vimshottari with reproducible UTC interval arithmetic."""

    dasha_depth: StrictInt = Field(
        default=2,
        ge=2,
        le=6,
        description="Vimshottari levels:2=MD/AD(default),3=PD,4=SD,5=PAD,6=DAD. Above2 adds the active ancestry and nine siblings per lower level, using complete-period fractions. The existing120-year timeline remains MD/AD only. Birth-grid variants follow all selected rulers; finer labels are not event precision or probabilities.",
    )

    analysis_timezone: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Civil target clock timezone, independent of the birth clock basis. Defaults to resolved birth civil timezone for civil input, or UTC for LMT/LAT input. It never changes the birth conversion or defines a solar target clock.",
    )

    analysis_year: Optional[int] = Field(
        default=None,
        ge=2,
        le=9800,
        description="Gregorian target year in analysis_timezone, else resolved birth civil zone or UTC for solar birth input. Omit to use that zone's date frozen by as_of/current clock; an explicit year defaults omitted month/day to January1.",
    )
    analysis_month: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Target Gregorian month (1..12). Defaults to January with an explicit analysis_year, otherwise the as_of/current local month. Supplying a month defaults an omitted day to 1.",
    )
    analysis_day: Optional[int] = Field(
        default=None,
        ge=1,
        le=31,
        description="Target Gregorian day, validated against the resolved year/month. Defaults to 1 when year or month is supplied; otherwise the as_of/current local day.",
    )
    analysis_hour: Optional[int] = Field(
        default=None,
        ge=0,
        le=23,
        description="Target civil-clock hour (0..23) in analysis_timezone or its declared default; defaults to00:00. Ambiguous DST target times require an explicit UTC offset for the target zone; the birth clock conversion remains independent.",
    )
    analysis_minute: Optional[int] = Field(
        default=None,
        ge=0,
        le=59,
        description="Target local civil-clock minute (0..59), paired with analysis_hour; omitted minutes default to 0. The result reports the resolved analysis_datetime and UTC period boundaries.",
    )
    year_basis: Literal["sidereal_365_25636", "tropical_365_2425", "savana_360"] = (
        Field(
            default="sidereal_365_25636",
            description="Fixed elapsed-day year convention, applied to all major/subperiod boundaries. No universal convention is implied.",
        )
    )

    @model_validator(mode="after")
    def _vedic_configuration(self) -> "AstroVimshottariRequest":
        if self.zodiacal not in {None, 1} or self.hsys not in {None, 0}:
            raise ValueError("Vimshottari uses Lahiri sidereal / whole-sign only")
        return self


class AstroChartPolyRequest(AstroIndiaRequest):
    """Polymorphic astro chart request (adds a chart_variant selector)."""

    apparent_model: Literal["native", "opaque_solar"] = Field(
        default="native",
        description="chart only: native retains the native chart. opaque_solar additionally returns standalone geocentric apparent_model_positions, with finite-source solar deflection outside an opaque 695700 km Sun and zero deflection for intercepted rays. Requires local barycentric ephemeris files and the jpl extra. This position layer does not recompute native planets, speeds, houses, aspects or readings; its tropical IAU2006/2000A frame is explicit even for a sidereal native chart.",
    )

    ephemeris_policy: Literal["auto", "require_data_files"] = Field(
        default="auto",
        json_schema_extra={"x-fatebridge-western-data-policy": True},
        description=(
            WesternEphemerisRequest.model_fields["ephemeris_policy"].description or ""
        )
        + " India retains its existing strict policy; Guolao accepts auto only.",
    )

    birth_timezone: Optional[str] = Field(
        default=None,
        description="Birth civil timezone: IANA name or UTC offset; a supported unambiguous birth_place may supply it. guolao_chart rejects unresolved missing timezones and does not derive a civil zone from longitude. Western variants and india_chart also reject unresolved civil zones before sky calculations; coordinates cannot establish the recorded zone. Explicit UTC is valid. Noncivil LMT/LAT input on supported variants requires this field omitted.",
    )

    use_true_solar_time: bool = Field(
        default=False,
        description=AstroChartRequest.model_fields["use_true_solar_time"].description,
    )

    birth_second: int = Field(
        default=0,
        ge=0,
        le=59,
        description="Recorded birth second for chart_variant=germany/chart13/india_chart/guolao_chart. Omitted seconds use the start of the supplied minute; this does not assert exact birth time. Other variants reject nonzero values.",
    )

    birth_microsecond: int = Field(
        default=0,
        ge=0,
        le=999999,
        description="Explicit fraction of the recorded birth second for india_chart/guolao_chart. Preserved numerically without certifying source-clock or astronomical accuracy. Other variants reject nonzero values.",
    )

    birth_clock_basis: Literal["civil", "local_mean_solar", "local_apparent_solar"] = (
        Field(
            default="civil",
            description="Confirmed birth clock basis. LMT/LAT are supported for germany/chart13/india_chart/guolao_chart and require birth_timezone omitted. Other solar-input variants require use_true_solar_time=false; Guolao may select its apparent hour without shifting the converted epoch, and LAT already supplies its nominal apparent hour. Guolao retains native TT/UT1 when UTC has no datetime carrier; other variants keep their declared representation limits. Solar-day or native-order ambiguity and unavailable month calendars remain explicit. Unknown historical clock bases are not inferred or calibrated.",
        )
    )

    chart_variant: str = Field(
        default="chart",
        description="Chart variant: chart, chart13, hellen_chart, guolao_chart, india_chart, germany",
    )
    analysis_datetime: Optional[AwareDatetime] = Field(
        default=None,
        description="Optional timezone-aware ISO target instant. germany: true-solar-arc geometry with a 365.25-day Julian symbolic key, not future observations. guolao_chart: source-ordinal small limit plus actual geocentric target sky, with explicit research calendar/model limits and no event probability. Other variants reject this option.",
    )
    guolao_month_basis: Optional[Literal["jie_month", "chinese_lunar_utc8"]] = Field(
        default=None,
        description=AstroGuolaoRequest.model_fields["guolao_month_basis"].description,
    )
    guolao_seasonal_anchor_policy: Optional[GuolaoSeasonalAnchorPolicy] = Field(
        default=None,
        description=AstroGuolaoRequest.model_fields[
            "guolao_seasonal_anchor_policy"
        ].description,
    )

    @model_validator(mode="after")
    def _solar_input_exclusions(self) -> "AstroChartPolyRequest":
        # Override the Indian-only validator inherited by this shared model.
        if self.birth_clock_basis != "civil" and (
            self.birth_timezone is not None
            or (self.use_true_solar_time and self.chart_variant != "guolao_chart")
        ):
            raise ValueError(
                "Local solar birth clocks require birth_timezone omitted; "
                "use_true_solar_time=true is only supported by guolao_chart"
            )
        return self

    @model_validator(mode="after")
    def _india_options_scope(self) -> "AstroChartPolyRequest":
        if self.apparent_model != "native" and self.chart_variant != "chart":
            raise ValueError("apparent_model=opaque_solar requires chart_variant=chart")
        if self.guolao_seasonal_anchor_policy is not None:
            if self.chart_variant != "guolao_chart":
                raise ValueError(
                    "guolao_seasonal_anchor_policy requires chart_variant=guolao_chart"
                )
            if self.guolao_seasonal_anchor_policy != "term_instants" and not (
                self.use_true_solar_time
                or self.birth_clock_basis == "local_apparent_solar"
            ):
                raise ValueError(
                    "Solar-day anchors require use_true_solar_time=true or explicit LAT input"
                )
        if self.guolao_month_basis is not None and (
            self.chart_variant != "guolao_chart" or self.analysis_datetime is None
        ):
            raise ValueError(
                "guolao_month_basis requires chart_variant=guolao_chart and analysis_datetime"
            )
        if self.birth_clock_basis != "civil":
            if self.chart_variant not in {
                "germany",
                "chart13",
                "india_chart",
                "guolao_chart",
            }:
                raise ValueError(
                    "Noncivil birth_clock_basis requires chart_variant=germany, chart13, india_chart or guolao_chart"
                )
        if self.birth_second and self.chart_variant not in {
            "germany",
            "chart13",
            "india_chart",
            "guolao_chart",
        }:
            raise ValueError(
                "nonzero birth_second requires chart_variant=germany, chart13, india_chart or guolao_chart"
            )
        if self.birth_microsecond and self.chart_variant not in {
            "india_chart",
            "guolao_chart",
        }:
            raise ValueError(
                "nonzero birth_microsecond requires chart_variant=india_chart or guolao_chart"
            )
        if self.analysis_datetime is not None and self.chart_variant not in {
            "germany",
            "guolao_chart",
        }:
            raise ValueError(
                "analysis_datetime requires chart_variant=germany or guolao_chart"
            )
        # MCP signatures materialize optional defaults before model validation.
        # Accept that neutral configuration on every existing chart variant;
        # reject Indian settings that would otherwise be silently discarded.
        customized = (
            self.node_mode != "mean"
            or self.saptavargaja_profile != "santhanam_27"
            or self.drekkana_profile != "santhanam_27_6"
            or self.cheshta_model != "unadjudicated"
            or self.divisions != [9, 10]
        )
        if self.chart_variant != "india_chart" and customized:
            raise ValueError(
                "custom node_mode/divisions/saptavargaja_profile/drekkana_profile/cheshta_model require chart_variant=india_chart"
            )
        if self.ephemeris_policy != "auto" and self.chart_variant == "guolao_chart":
            raise ValueError("Western ephemeris_policy is not implemented for Guolao")
        if (
            self.birth_time_uncertainty_minutes is not None
            and self.chart_variant not in {"india_chart", "germany", "chart13"}
        ):
            raise ValueError(
                "birth_time_uncertainty_minutes requires chart_variant=india_chart, germany or chart13"
            )
        return self

    def uses_western_ephemeris_policy(self) -> bool:
        return self.chart_variant not in {"india_chart", "guolao_chart"}


class AstroRelativeFlatRequest(WesternEphemerisRequest):
    """Flat (non-nested) relative/synastry chart request for tool surfaces."""

    davison_variant: Literal["uncorrected", "corrected", "spherical"] = Field(
        default="uncorrected",
        description="TimeSpace/Marks variant: uncorrected, MC-axis corrected, or spherical geographic midpoint. UT1 arithmetic time mean; nondefault variants require TimeSpace or Marks.",
    )

    inner_use_true_solar_time: bool = Field(
        default=False, description="Use apparent solar time for the inner chart"
    )
    outer_use_true_solar_time: bool = Field(
        default=False, description="Use apparent solar time for the outer chart"
    )

    inner_birth_year: int = Field(description="Inner chart birth year")
    inner_birth_month: int = Field(ge=1, le=12, description="Inner chart birth month")
    inner_birth_day: int = Field(ge=1, le=31, description="Inner chart birth day")
    inner_birth_hour: int = Field(ge=0, le=23, description="Inner chart birth hour")
    inner_birth_longitude: float = Field(ge=-180, le=180, description="Inner longitude")
    inner_birth_latitude: float = Field(ge=-90, le=90, description="Inner latitude")
    outer_birth_year: int = Field(description="Outer chart birth year")
    outer_birth_month: int = Field(ge=1, le=12, description="Outer chart birth month")
    outer_birth_day: int = Field(ge=1, le=31, description="Outer chart birth day")
    outer_birth_hour: int = Field(ge=0, le=23, description="Outer chart birth hour")
    outer_birth_longitude: float = Field(ge=-180, le=180, description="Outer longitude")
    outer_birth_latitude: float = Field(ge=-90, le=90, description="Outer latitude")
    inner_name: Optional[str] = Field(default="内盘", description="Inner chart name")
    outer_name: Optional[str] = Field(default="外盘", description="Outer chart name")
    inner_birth_place: Optional[str] = Field(
        default="未提供", description="Inner birth place"
    )
    outer_birth_place: Optional[str] = Field(
        default="未提供", description="Outer birth place"
    )
    relative_mode: Optional[Union[str, int]] = Field(
        default=None, description="Relative mode selector"
    )
    inner_birth_minute: int = Field(
        default=0, ge=0, le=59, description="Inner birth minute"
    )
    outer_birth_minute: int = Field(
        default=0, ge=0, le=59, description="Outer birth minute"
    )
    inner_birth_timezone: Optional[str] = Field(
        default=None,
        description=(
            "Inner timezone (IANA name or UTC offset). Optional: when omitted, "
            "FateBridge may resolve it from supported inner_birth_place; no implicit "
            "UTC is selected when unresolved. A hardcoded 'UTC' default silently "
            "treated an eastern wall-clock time as UTC and rotated the chart."
        ),
    )
    outer_birth_timezone: Optional[str] = Field(
        default=None,
        description=(
            "Outer timezone (IANA name or UTC offset). Optional: when omitted, "
            "FateBridge may resolve it from supported outer_birth_place; no implicit "
            "UTC is selected when unresolved. A hardcoded 'UTC' default silently "
            "treated an eastern wall-clock time as UTC and rotated the chart."
        ),
    )
    hsys: int = Field(
        default=3,
        ge=0,
        le=8,
        description="House system identifier (0..8). Defaults to Placidus (3) to "
        "match the natal chart." + OFFLINE_HOUSE_CODE_NOTE,
    )
    zodiacal: int = Field(default=0, description="Zodiac selector")
    relationship_focus: Optional[str] = Field(
        default=None,
        description=(
            "Optional relationship intent lens: marriage/婚姻 or romance/恋爱; "
            "adds a focus block + intent-filtered synastry aspects. Default/unset "
            "is general (no filtering)."
        ),
    )
