"""Clock policy and actual solar-term dependencies for Liu Ren / Jin Kou."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from ...utils.civil_clock import format_utc_offset, resolve_civil_clock, utc_instant
from ...utils.errors import EphemerisSourceError
from ...utils.places import DEFAULT_BIRTH_TIMEZONE, resolve_birth_place_context
from ...utils.timezones import timezone_rules_metadata
from ..almanac import (
    SolarTerm,
    get_adjacent_solar_terms,
    get_bazi_month_boundaries,
    get_solar_terms_for_year,
    is_calculated_solar_term,
    localize_datetime,
)
from ..analytic_solar import MODEL_ID as ANALYTIC_SOLAR_MODEL
from ..solar_term_runtime import loaded_clock_profile_key
from .common import MetaphysicsSeed
from .hko_term_dates import published_date_reference
from .ren_term_longitude import validate_term_longitude
from .ren_term_point import validate_term_point


def resolve_runyear_birth_zone(
    explicit_timezone: str | None,
    birth_place: str | None,
    birth_longitude: float | None = None,
) -> tuple[str, dict[str, Any]]:
    """Resolve a civil zone without requiring or applying a birth solar clock."""
    canonical = None
    advisory = None
    if explicit_timezone is not None:
        zone = explicit_timezone.strip()
        if not zone:
            raise ValueError("行年birth_timezone不能为空；请提供民用时区或省略该字段")
        source = "birth_timezone"
    elif birth_place and birth_place.strip() not in ("", "未提供"):
        place = resolve_birth_place_context(birth_place)
        if place.timezone is None:
            raise ValueError(
                "行年出生地无法唯一解析民用时区；请补全国家、省市或明确birth_timezone"
            )
        zone = place.timezone
        canonical = place.canonical_name
        source = "birth_place"
    elif birth_longitude is not None:
        raise ValueError(
            "行年不能仅凭出生经度确定民用时区；请明确birth_timezone或提供可解析出生地"
        )
    else:
        zone = DEFAULT_BIRTH_TIMEZONE
        source = "default_timezone"
        advisory = "未提供出生民用时区或出生地，沿用Asia/Shanghai软件默认；未核实实际出生时区。"
    return zone, {
        "timezone_source": source,
        "timezone_resolved_place": canonical,
        "timezone_assumed": source == "default_timezone",
        "timezone_resolution_advisory": advisory,
    }


def resolve_runyear_birth_clock(
    wall: datetime,
    timezone_name: str,
    explicit_offset: str | None = None,
    *,
    recorded_offset: str | None = None,
) -> tuple[datetime, dict[str, Any]]:
    """Validate the birth civil label independently of the analysis clock."""
    try:
        civil = resolve_civil_clock(
            wall, timezone_name, explicit_offset, recorded_offset=recorded_offset
        )
    except ValueError as error:
        raise ValueError(
            "行年出生民用时刻："
            + str(error).replace("analysis_utc_offset", "birth_utc_offset")
        ) from error
    offset = civil.utcoffset()
    assert offset is not None
    return civil, {
        "method": "validated_birth_civil_clock",
        "timezone": timezone_name,
        "input_utc_offset": (
            explicit_offset if explicit_offset is not None else recorded_offset
        ),
        "resolved_utc_offset": format_utc_offset(offset),
        "wall_datetime": civil.replace(tzinfo=None).isoformat(),
        "was_ambiguous": civil.replace(fold=0).utcoffset()
        != civil.replace(fold=1).utcoffset(),
        "fold": civil.fold,
        "instant_utc": utc_instant(civil).isoformat(),
        "timezone_rules": timezone_rules_metadata(timezone_name),
    }


def _term_time_scale(moment: datetime) -> dict[str, Any]:
    # A repeated civil moment can have new expiry/source metadata even if
    # its numerical UTC/TT conversion is unchanged. Keep the receipt on the
    # same loaded profile as the term solver, not merely on the same moment.
    for _ in range(3):
        profile = loaded_clock_profile_key()
        result = _term_time_scale_cached(moment, profile)
        if loaded_clock_profile_key() == profile:
            return result
        _term_time_scale_cached.cache_clear()
    raise RuntimeError("Civil time profile changed during term receipt calculation")


@lru_cache(maxsize=2048)
def _term_time_scale_cached(moment: datetime, _profile: str) -> dict[str, Any]:
    from fatebridge.core.astro.utc_policy import leap_table

    from ..astro.time_scales import ephemeris_time

    epoch = ephemeris_time(moment)
    table = leap_table()
    return {
        "solver_time_scale": "TT",
        "civil_time_method": epoch.method,
        "future_leap_seconds_assumed_unchanged": epoch.future_leap_seconds_assumed_unchanged,
        "leap_table_expires_at": table["expires_at"],
        "leap_table_source": table["source_url"],
    }


for _cache_attribute in ("cache_clear", "cache_info", "cache_parameters"):
    setattr(
        _term_time_scale,
        _cache_attribute,
        getattr(_term_time_scale_cached, _cache_attribute),
    )


def require_ren_solar_term(term: SolarTerm) -> None:
    """Check the consumed boundary, including the loaded model's own frame.

    A named provider is a source receipt, never an accuracy certificate. In
    particular, packaged DE440 must not acquire Swiss flags or a different
    coordinate definition while retaining its legitimate orbit hashes.
    """
    provider = term.resolution_provider
    if (
        provider
        in {
            "fatebridge_analytic",
            "fatebridge_moshier",
            "jpl_spk",
            "jpl_de440",
            "moshier_aa1996",
            "vsop2013",
        }
        and term.ephemeris_retflags
    ):
        raise RuntimeError("独立太阳模型不能借用原生星历返回标志")
    if not is_calculated_solar_term(term):
        raise RuntimeError(
            "六壬与金口诀需要 swisseph 或具名独立太阳模型的天文交气，不能以线性或未知节气值起课"
        )
    if provider == "swisseph":
        if term.ephemeris_model not in {"swieph", "moshier", "jpl"}:
            raise RuntimeError("六壬与金口诀交气的实际星历模型未知，不能认证计算来源")
        model_flags = {"jpl": 1, "swieph": 2, "moshier": 4}
        if not term.ephemeris_retflags or any(
            type(flag) is not int or flag not in (1, 2, 4)
            for flag in term.ephemeris_retflags
        ):
            raise RuntimeError(
                "六壬与金口诀交气黄经选项未知，不能认证默认地心视黄经定义"
            )
        if any(
            flag != model_flags[term.ephemeris_model]
            for flag in term.ephemeris_retflags
        ):
            raise RuntimeError("六壬与金口诀交气模型回执与原生返回标志不一致")
    if provider == "jpl_de440":
        from ..de440_solar import source_receipt

        expected = source_receipt(term.ephemeris_model)
        details = term.solar_model_details or {}
        # Canonical JSON also distinguishes true/1 and false/0. Compare every
        # source/geometry claim, not just the orbit hash or provider string.
        observed = {key: details.get(key) for key in expected}
        try:
            matches = json.dumps(
                observed, sort_keys=True, allow_nan=False
            ) == json.dumps(expected, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError):
            matches = False
        if (
            not matches
            or details.get("numerical_resolution_is_physical_accuracy") is not False
        ):
            raise EphemerisSourceError("solar_de440_invalid")
    try:
        validate_term_point(term.solar_model_details, term.moment, complete=True)
    except EphemerisSourceError:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise EphemerisSourceError("ren_solar_term_point_inconsistent") from exc
    validate_term_longitude(
        name=term.name,
        provider=term.resolution_provider,
        model=term.ephemeris_model,
        flags=term.ephemeris_retflags,
        library_version=term.ephemeris_library_version,
        details=term.solar_model_details,
        complete=True,
    )


def require_ren_calendar(
    seed: MetaphysicsSeed,
    *,
    month_general_override: str | None = None,
    analysis_utc_offset: str | None = None,
) -> dict[str, Any]:
    civil = localize_datetime(seed.input_datetime, seed.timezone)
    clock = seed.corrected_datetime
    current, following = get_adjacent_solar_terms(civil, seed.timezone)
    month, next_month, _, _ = get_bazi_month_boundaries(civil, seed.timezone)
    spring = next(
        t
        for t in get_solar_terms_for_year(civil.year, seed.timezone)
        if t.name == "立春"
    )
    term_dependencies = (
        ("current_term", current),
        ("next_term", following),
        ("month_start", month),
        ("next_month_start", next_month),
        ("year_boundary", spring),
    )
    for _, term in term_dependencies:
        require_ren_solar_term(term)
    dependencies: list[dict[str, Any]] = [
        {
            "role": role,
            "name": term.name,
            "civil_moment": term.moment.isoformat(),
            "provider": term.resolution_provider,
            "ephemeris_model": term.ephemeris_model,
            "ephemeris_retflags": list(term.ephemeris_retflags),
            "ephemeris_library_version": term.ephemeris_library_version,
            "published_date_reference": published_date_reference(
                term.name, term.moment
            ),
            **(
                {"solar_model_details": term.as_dict()["solar_model_details"]}
                if term.solar_model_details is not None
                else {}
            ),
        }
        for role, term in term_dependencies
    ]
    for entry in dependencies:
        entry.update(_term_time_scale(datetime.fromisoformat(entry["civil_moment"])))
    result: dict[str, Any] = {
        "mode": "civil_instant_checked",
        "civil_datetime": civil.isoformat(),
        "civil_instant_utc": civil.astimezone(timezone.utc).isoformat(),
        "day_hour_clock": "apparent_solar" if seed.applied_true_solar else "civil",
        "corrected_clock": (
            clock.replace(tzinfo=None).isoformat()
            if seed.applied_true_solar
            else clock.isoformat()
        ),
        "day_boundary": "23:00",
        "effective_day_date": (
            clock.date() + timedelta(days=int(clock.hour == 23))
        ).isoformat(),
        "effective_day_ganzhi": "".join(seed.pillars["day"]),
        "year_month_clock": "civil_instant",
        "month_general_clock": (
            "explicit_symbolic_override" if month_general_override else "civil_instant"
        ),
        "month_general_override": month_general_override,
        "month_boundary": "节换月",
        "month_general_boundary": (
            "显式月将覆盖中气规则" if month_general_override else "中气换将"
        ),
        "solar_term_dependencies": dependencies,
        "solar_longitude_definition": {
            "origin": "geocentric",
            "position": "apparent",
            "plane": "ecliptic_of_date",
            "equinox": "true_of_date",
            "astronomical_model": "Swiss_Ephemeris_default_IERS2010_Astronomical_Almanac",
            "horizons_frame_equivalence_certified": False,
            "source_url": "https://www.astro.com/swisseph/swephprg.htm",
            "source_section": "3.3.5: True or mean equinox of date; JPL Horizons positions",
            "scope": "当前交气求解请求Swiss默认地心视黄经；JPL Horizons的IAU76/80与EOP参考系不同，不能将跨参考系残差直接等同于同一定义下的误差",
        },
        "precision_status": "TT_solver_explicit_civil_time_policy_not_full_domain_certification",
        "scope": "23时子初换日为当前软件约定；真太阳钟只用于日时柱，交节仍用民用瞬间；天文求解使用TT，1960年前采用历史UT1标记约定，1960年用SOFA历史UTC偏移与日漂移，1961至1971年用IERS历史UTC漂移，其后用冻结闰秒表；未来闰秒保持末值是假设。小数秒仅数值分辨率，提供者状态不代替独立天文精度核验",
    }
    from fatebridge.core.aa1996_solar import MODEL_ID as AA1996_SOLAR_MODEL
    from fatebridge.core.de440_solar import EXTENDED_MODEL_ID as DE440_EXTENDED_MODEL
    from fatebridge.core.de440_solar import MODEL_ID as DE440_SOLAR_MODEL
    from fatebridge.core.moshier_solar import MODEL_ID as COMPLETE_MOSHIER_SOLAR_MODEL
    from fatebridge.core.spk_solar import MODEL_ID as SPK_SOLAR_MODEL
    from fatebridge.core.vsop2013_solar import MODEL_ID as VSOP2013_SOLAR_MODEL

    if any(
        t["ephemeris_model"]
        in {
            ANALYTIC_SOLAR_MODEL,
            SPK_SOLAR_MODEL,
            DE440_SOLAR_MODEL,
            DE440_EXTENDED_MODEL,
            AA1996_SOLAR_MODEL,
            COMPLETE_MOSHIER_SOLAR_MODEL,
            VSOP2013_SOLAR_MODEL,
        }
        for t in dependencies
    ):
        models = {t["ephemeris_model"] for t in dependencies}
        result["solar_longitude_definition"] = {
            "origin": "geocentric",
            "position": "apparent",
            "plane": "ecliptic_of_date",
            "equinox": "true_of_date",
            "astronomical_model": (
                ANALYTIC_SOLAR_MODEL
                if models == {ANALYTIC_SOLAR_MODEL}
                else "per_dependency_named_models"
            ),
            "horizons_frame_equivalence_certified": False,
            "source_url": (
                current.solar_model_details["source_url"]
                if current.solar_model_details
                else "https://www.astro.com/swisseph/swephprg.htm"
            ),
            "source_section": "Per-boundary model details: ERFA epv00/pfw06/nut00b or native Swiss source",
            "scope": "逐交气列出实际模型；具名解析模型使用ERFA简化VSOP2000、IAU2006/P03与IAU2000B日期真黄道。没有将其更名为Swiss默认IERS2010或认证与Horizons参考系等同；TT替代TDB及作者范围警告见各边界元数据。",
        }
        if SPK_SOLAR_MODEL in models:
            result["solar_longitude_definition"].update(
                source_section="Per-boundary JPL SPK vectors, ERFA dtdb, IAU2006/P03 and IAU2000B",
                scope="逐交气保留实际SPK文件散列、TDB覆盖与参考系；不借用Swiss原生返回标志或将有限比较认证为绝对UTC、Horizons等同或完整物理精度。",
            )
        if models & {DE440_SOLAR_MODEL, DE440_EXTENDED_MODEL}:
            result["solar_longitude_definition"].update(
                source_section="Per-boundary losslessly extracted DE440 coefficients, geocentric ERFA Fairhead TDB, IAU2006/P03 and IAU2000B",
                scope="逐交气保留实际载入系数及原始SPK来源的不同散列、TDB覆盖与参考系；FateBridge裁取系数产品的生产者另列。原始内核来源不等于运行时加载了完整SPK，也不认证绝对UTC、Horizons等同或完整物理精度。",
            )
        if AA1996_SOLAR_MODEL in models:
            result["solar_longitude_definition"].update(
                source_section="Per-boundary AA1996 EMB and full Moshier Moon, complete Swiss2.10.03 native apparent recomputation",
                scope="逐交气保留改版模型的实际二进制、源图与配置散列；底层Moshier类别标志不代表原版模型身份，不将有限数值比较认证为全部时刻、民用时制或Horizons等同。",
            )
        if COMPLETE_MOSHIER_SOLAR_MODEL in models:
            result["solar_longitude_definition"].update(
                source_section="Per-boundary complete Moshier December 1996 EMB, full native geometric Moon, IAU2006/P03 and IAU2000B",
                scope="逐交气记录完整Moshier修订的系数来源、月球原生依赖与参考系；不重标为原版Swiss默认太阳，也不以有限TT对照认证整个时域、绝对UTC或预测。",
            )
        if VSOP2013_SOLAR_MODEL in models:
            result["solar_longitude_definition"].update(
                source_section="Per-boundary complete VSOP2013 EMB and full Moshier Moon, geocentric ERFA TT-to-TDB and Swiss2.10.03 apparent recomputation",
                scope="逐交气保留具名VSOP2013模型的实际二进制、配置与源图散列；内部Moshier类别选项不是原生模型身份。TT有限对照不认证绝对UTC、所有连续时刻或Horizons参考系等同。",
            )
    if analysis_utc_offset is not None:
        resolved = resolve_civil_clock(
            civil.replace(tzinfo=None, fold=0), seed.timezone, analysis_utc_offset
        )
        if utc_instant(resolved) != utc_instant(civil):
            raise ValueError("明确UTC偏移与起课实际民用瞬间不一致")
        offset = resolved.utcoffset()
        assert offset is not None
        result["civil_clock_resolution"] = {
            "method": "explicit_offset_checked_against_analysis_timezone",
            "timezone": seed.timezone,
            "input_utc_offset": analysis_utc_offset,
            "resolved_utc_offset": format_utc_offset(offset),
            "wall_datetime": civil.replace(tzinfo=None).isoformat(),
            "was_ambiguous": (
                resolved.replace(fold=0).utcoffset()
                != resolved.replace(fold=1).utcoffset()
            ),
            "fold": resolved.fold,
            "instant_utc": utc_instant(resolved).isoformat(),
            "timezone_rules": timezone_rules_metadata(seed.timezone),
        }
    return result


def symbolic_calendar_policy() -> dict[str, Any]:
    return {
        "mode": "symbolic_or_unverified_civil_input",
        "precision_status": "not_a_civil_calendar_validation",
        "scope": "仅按所给日干支、时支和节气符号推演；未据此认证某个真实公历时刻",
    }
