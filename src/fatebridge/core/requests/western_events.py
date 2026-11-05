"""Request contracts for western events."""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from fatebridge.core.requests.western_lifespan import AstroLifespanRequest
from fatebridge.core.requests.western_policy import WesternEphemerisRequest
from fatebridge.utils.house_systems import TWELVE_HOUSE_SYSTEM_NOTE


class AstroMundaneRequest(WesternEphemerisRequest):
    """Request model for the 世俗入宫盘 (mundane ingress) tool — cast at a solar ingress, no birth data."""

    name: Optional[str] = Field(default=None, description="Optional chart name")
    year: int = Field(description="Civil year of the ingress, e.g. 2026")
    ingress_term: Literal["春分", "夏至", "秋分", "冬至"] = Field(
        default="春分",
        description="Cardinal ingress: 春分 (spring equinox) / 夏至 / 秋分 / 冬至",
    )
    longitude: float = Field(
        ge=-180,
        le=180,
        description="Observation longitude (e.g. capital / place of interest)",
    )
    latitude: float = Field(ge=-90, le=90, description="Observation latitude")
    timezone_name: str = Field(
        default="+08:00", description="Observation timezone (IANA name or UTC offset)"
    )
    house_system: Union[int, str] = Field(
        default="P",
        description="House system, any convention: SE letter ('P'=Placidus, "
        "'R'=Regiomontanus, 'W'=whole sign, 'D'=equal_mc), key ('placidus', "
        "'equal_mc'), or integer code 0..8 (3=Placidus, 8=equal_mc)."
        + TWELVE_HOUSE_SYSTEM_NOTE,
    )
    zodiac_type: str = Field(
        default="Tropic", description="Zodiac type, e.g. Tropic or Sidereal"
    )


class AstroExtraReturnsRequest(AstroLifespanRequest):
    """Request model for the 多重回归 (Saturn/Jupiter/node returns) tool."""

    analysis_year: Optional[int] = Field(
        default=None,
        description="Reference year for the returns (omit for current date)",
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Reference month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Reference day (1-31)"
    )


class LillyRadicalityContext(BaseModel):
    """Optional caller reports for source exceptions, never inferred facts."""

    model_config = ConfigDict(extra="forbid")
    figure_origin: Optional[
        Literal["propounded_question", "timed_event", "unknown"]
    ] = Field(
        default=None,
        description="Optional reported origin; timed_event only supplies context for the p122 exception, not a complete event-astrology method. Omission uses this API's question-instant convention.",
    )
    very_young_querent_reported: Optional[StrictBool] = None
    rising_description_agreement_reported: Optional[StrictBool] = None
    age_degree_agreement_reported: Optional[StrictBool] = None
    event_time_certain_reported: Optional[StrictBool] = Field(
        default=None,
        description="Caller reports a certain event instant; a valid date or known question time does not establish this.",
    )
    principal_significators_very_strong_reported: Optional[StrictBool] = None
    seventh_cusp_afflicted_reported: Optional[StrictBool] = None
    seventh_lord_impeded_reported: Optional[StrictBool] = None
    seventh_lord_unfortunate_reported: Optional[StrictBool] = None
    equal_fortune_infortune_testimonies_reported: Optional[StrictBool] = Field(
        default=None,
        description="Reported testimony balance; not derived from p115 weighted score0. All context reports are unverified and optional.",
    )


class AstroHoraryRequest(WesternEphemerisRequest):
    """Request model for the 卜卦 (horary) tool — chart cast at the question moment."""

    name: Optional[str] = Field(default=None, description="Optional chart name")
    ut1_source: Literal["swiss_delta_t", "iers_c04"] = Field(
        default="swiss_delta_t",
        description="Earth-rotation time source: legacy Swiss Delta T model(default), or pinned IERS20 C04 final daily UT1 series,1962-01-01T00:00UTC..2026-09-19T00:00UTC. C04 uses continuous UT1-TAI interpolation; no out-of-range prediction/extrapolation/model fallback. Does not apply polar motion,CIP offsets or subdaily tides and does not certify clock-record precision. Geocentric TT longitude-event searches need no trial UT1; houses and horizon calculations still require covered UT1 epochs.",
    )
    question_hour_origin: Literal["midnight", "noon"] = Field(
        default="midnight",
        description="Hour-label origin, independent of civil/LMT/LAT: midnight(default) hour0=00:00; noon hour0=same-date12:00 and hour12..23=next-date00:00..11:00. Select noon only for confirmed noon-based labels, e.g. Lilly1647 pp30-31 ephemeris tables, not all charts. Nominal labels, not elapsed duration, timezone or JD epoch correction. Calendar and day carry normalize before timezone validation.",
    )
    question_year: int = Field(description="Year the question was asked")
    question_calendar: Literal["proleptic_gregorian", "julian"] = Field(
        default="proleptic_gregorian",
        description="Explicit calendar for question date labels; CE year starts Jan1. No country reform, March25 year rollover or historical clock inferred. Converted before the supplied timezone is applied.",
    )
    question_month: int = Field(
        ge=1, le=12, description="Month the question was asked (1-12)"
    )
    question_day: int = Field(
        ge=1, le=31, description="Day the question was asked (1-31)"
    )
    question_hour: int = Field(
        ge=0, le=23, description="Hour the question was asked (0-23)"
    )
    question_minute: int = Field(
        default=0, ge=0, le=59, description="Minute the question was asked"
    )
    question_clock_basis: Literal[
        "civil", "local_mean_solar", "local_apparent_solar"
    ] = Field(
        default="civil",
        description="Explicit question clock: civil zone clock, local mean solar (UT1 + east longitude/360), or geocentric local apparent solar (adds EOT). Do not infer an original author's clock by fitting the chart. Solar labels require timezone_name omitted/null.",
    )
    timezone_name: Optional[str] = Field(
        default=None,
        description="Civil question timezone (IANA or UTC offset). Omitted/null with civil preserves legacy +08:00; supply the known zone explicitly. Solar clock bases must omit/null this field to prevent double correction.",
    )
    longitude: float = Field(
        ge=-180, le=180, description="Longitude where the question was asked"
    )
    latitude: float = Field(
        ge=-90, le=90, description="Latitude where the question was asked"
    )
    category: Literal[
        "general",
        "wealth",
        "family",
        "property",
        "marriage",
        "lawsuit",
        "theft",
        "travel",
        "career",
        "hope",
        "enemy",
    ] = Field(
        default="general",
        description=(
            "Question topic, selecting the quesited house: general/wealth/family/"
            "property/marriage/lawsuit/theft/travel/career/hope/enemy; "
            "生死、疾病与生育临床判断不开放"
        ),
    )
    orb_profile: Literal["lilly_1647_p107_first", "lilly_1647_p107_second"] = Field(
        default="lilly_1647_p107_first",
        description="Lilly1647 p107 printed full-orb column. Both source variants are supported; pair radius is their half-sum. First column matches the printed Saturn/Venus moiety example.",
    )
    radicality_context: Optional[LillyRadicalityContext] = Field(
        default=None,
        description="Optional already-known reports for Lilly pp121-123 prerequisites and exceptions. Unknown reports remain unknown; do not infer age, appearance, affliction or event certainty to clear a caution.",
    )
    house_system: Union[int, str] = Field(
        default="R",
        description="House system, any convention (SE letter / key / integer "
        "code 0..8); Regiomontanus (R, code 2) is traditional for horary."
        + TWELVE_HOUSE_SYSTEM_NOTE,
    )
    zodiac_type: str = Field(
        default="Tropic", description="Zodiac type, e.g. Tropic or Sidereal"
    )

    @model_validator(mode="after")
    def _exclusive_question_clock(self) -> "AstroHoraryRequest":
        if self.question_clock_basis != "civil" and self.timezone_name is not None:
            raise ValueError("Solar question clock must omit timezone_name")
        return self


class AstroElectionRequest(WesternEphemerisRequest):
    """Request model for the 择日 (electional) tool — chart cast at the candidate moment."""

    name: Optional[str] = Field(default=None, description="Optional chart name")
    ut1_source: Literal["swiss_delta_t", "iers_c04"] = Field(
        default="swiss_delta_t",
        description="Earth-rotation time source: legacy Swiss Delta T model(default), or pinned IERS20 C04 final daily UT1 series,1962-01-01T00:00UTC..2026-09-19T00:00UTC. No prediction/extrapolation/model fallback outside coverage; UT1-only correction, not full EOP. Geocentric TT longitude-event searches need no trial UT1; houses and horizon calculations still require covered UT1 epochs.",
    )
    candidate_hour_origin: Literal["midnight", "noon"] = Field(
        default="midnight",
        description="Explicit hour-label origin: midnight(default) hour0=00:00; noon hour0=same-date12:00 and hour12..23=next-date00:00..11:00. Confirm the source convention first; independent of civil/LMT/LAT, never an elapsed duration, timezone offset or automatic historical inference. Normalize calendar/day carry before applying timezone.",
    )
    candidate_calendar: Literal["proleptic_gregorian", "julian"] = Field(
        default="proleptic_gregorian",
        description="Explicit calendar for candidate date labels; CE Jan1 years, no automatic regional reform or old-style year/clock reconstruction. Normalize date labels before applying timezone.",
    )
    candidate_year: int = Field(
        description="Year of the candidate moment being evaluated"
    )
    candidate_month: int = Field(
        ge=1, le=12, description="Month of the candidate moment (1-12)"
    )
    candidate_day: int = Field(
        ge=1, le=31, description="Day of the candidate moment (1-31)"
    )
    candidate_hour: int = Field(
        ge=0, le=23, description="Hour of the candidate moment (0-23)"
    )
    candidate_minute: int = Field(
        default=0, ge=0, le=59, description="Minute of the candidate moment"
    )
    candidate_clock_basis: Literal[
        "civil", "local_mean_solar", "local_apparent_solar"
    ] = Field(
        default="civil",
        description="Explicit candidate clock: civil, local mean solar (UT1 + east longitude/360), or geocentric local apparent solar (adds EOT). Solar labels require timezone_name omitted/null; unknown original clocks stay unknown.",
    )
    timezone_name: Optional[str] = Field(
        default=None,
        description="Civil candidate timezone (IANA or UTC offset). Omitted/null with civil preserves legacy +08:00; use the known zone explicitly. Omit/null for solar clock bases, never combine both corrections.",
    )
    longitude: float = Field(
        ge=-180, le=180, description="Longitude where the act will take place"
    )
    latitude: float = Field(
        ge=-90, le=90, description="Latitude where the act will take place"
    )
    topic_id: Literal[
        "marriage",
        "business",
        "move_in",
        "buy_property",
        "trade",
        "buy_car",
        "contract",
        "travel",
        "job_hunt",
        "general",
    ] = Field(
        default="marriage",
        description=(
            "Undertaking type, selecting the rule pack: marriage/business/move_in/"
            "buy_property/trade/buy_car/contract/travel/job_hunt/general; 不提供医疗择时"
        ),
    )
    house_system: Union[int, str] = Field(
        default="R",
        description="House system, any convention (SE letter / key / integer "
        "code 0..8); Regiomontanus (R, code 2) is traditional for elections."
        + TWELVE_HOUSE_SYSTEM_NOTE,
    )
    zodiac_type: str = Field(
        default="Tropic", description="Zodiac type, e.g. Tropic or Sidereal"
    )

    @model_validator(mode="after")
    def _exclusive_candidate_clock(self) -> "AstroElectionRequest":
        if self.candidate_clock_basis != "civil" and self.timezone_name is not None:
            raise ValueError("Solar candidate clock must omit timezone_name")
        return self
