"""Source-defined TT ordering without rounding civil microseconds into one JD.

This axis is for input ordering only. Astronomical evaluations keep their
original binary64 epochs. Historical UT1 still depends on observed native
Delta T, which is replayable evidence and is not independently authenticated.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from importlib.resources import files
from typing import Any, cast

from fatebridge.core.astro import runtime
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.human_design_birth_clock import resolve_birth_clock
from fatebridge.utils.civil_time import datetime_fromisoformat_preserving_offset

METHOD = "human_design_source_defined_reference_order_v1"
SCOPE = "仅以源定义的连续TT有理数核对输入先后，保留民用钟微秒和UTC漂移系数；1960年前仍按历史UT1与实际原生DeltaT约定。星历计算仍使用原有双精度TT，不认证微秒级天文精度、出生记录、原生执行真实性或现实预测。冻结闰秒表到期后沿用末项仍是假设。"
DAY_US = 86_400_000_000
TOLERANCE_SECONDS = Fraction(1, 5000)


def validate_reference_precision(value: str) -> None:
    # datetime.fromisoformat silently truncates extra fractional digits. Reject
    # these before parsing, including fractional UTC offsets and comma syntax.
    if re.search(r"[.,]\d{7,}", value):
        raise ValueError("cycle_reference_datetime 的小数秒最多6位，不静默截断")


def civil_jd(moment: datetime) -> Fraction:
    if moment.utcoffset() is None:
        raise ValueError("An aware civil clock is required")
    utc = moment.astimezone(timezone.utc)
    micros = ((utc.hour * 60 + utc.minute) * 60 + utc.second) * 1_000_000
    return Fraction(2 * utc.toordinal() + 3442849, 2) + Fraction(
        micros + utc.microsecond, DAY_US
    )


def _source(name: str) -> tuple[dict[str, Any], dict[str, str]]:
    raw = files("fatebridge.data").joinpath(f"knowledge/{name}.json").read_bytes()
    table = json.loads(raw)
    return table, {
        "table": name,
        "table_sha256": hashlib.sha256(raw).hexdigest(),
        "source_url": table["source_url"],
        "source_document_sha256": table["source_sha256"],
    }


def _finite(value: Any) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("Ordering witness requires finite binary64 epochs")
    return value


def _close(a: Fraction, b: float) -> None:
    if abs(a - Fraction(_finite(b))) * 86400 > TOLERANCE_SECONDS:
        raise ValueError("Ordering axis is detached from the physical epoch")


@runtime.preserve_ephemeris_path()
def _historical_native(moment: datetime) -> dict[str, Any]:
    if runtime.swe is None:
        raise ImportError("Swiss Ephemeris required for historical UT1")
    runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
    args = [
        moment.year,
        moment.month,
        moment.day,
        moment.hour,
        moment.minute,
        moment.second + moment.microsecond / 1e6,
        runtime.swe.GREG_CAL,
    ]
    tt, ut1 = runtime.ephemeris_call("utc_to_jd", *args)
    delta = runtime.ephemeris_call("deltat_ex", ut1, -1)
    return {
        "utc_to_jd_arguments": args,
        "jd_tt": float(tt),
        "jd_ut1": float(ut1),
        "delta_t_flag": -1,
        "delta_t_days": float(delta),
    }


def _axis(
    label: str | None,
    physical_tt: float,
    *,
    replay: bool,
    native: dict[str, Any] | None,
) -> tuple[Fraction, dict[str, Any]]:
    _finite(physical_tt)
    proof: dict[str, Any] = {"utc_label": label, "physical_jd_tt": physical_tt}
    if label is None:
        exact = Fraction(physical_tt)
        proof["source"] = {"method": "literal_binary64_TT_without_civil_input"}
    else:
        validate_reference_precision(label)
        leap = label[17:19] == "60"
        moment = datetime_fromisoformat_preserving_offset(
            (label[:17] + "59" + label[19:] if leap else label).replace("Z", "+00:00")
        )
        if moment.utcoffset() != timedelta(0):
            raise ValueError("Ordering clock must be normalized UTC")
        if leap:
            clock = resolve_birth_clock(
                birth_year=moment.year,
                birth_month=moment.month,
                birth_day=moment.day,
                birth_hour=moment.hour,
                birth_minute=moment.minute,
                birth_second=60,
                birth_timezone="UTC",
            )
            assert clock.evidence is not None
            _, source = _source("western-leap-seconds")
            offset = clock.evidence["tai_minus_utc_during_leap_seconds"]
            following = moment.replace(microsecond=0) + timedelta(seconds=1)
            exact = (
                civil_jd(following)
                + (
                    offset
                    + Fraction(32184, 1000)
                    + Fraction(moment.microsecond, 1_000_000)
                )
                / 86400
            )
            proof["source"] = {
                **source,
                "method": "confirmed_positive_UTC_leap_second",
                "tai_minus_utc_seconds": offset,
            }
        elif moment.year >= 1960:
            table, source = _source(
                "western-utc1960"
                if moment.year == 1960
                else (
                    "western-historical-utc"
                    if moment.year < 1972
                    else "western-leap-seconds"
                )
            )
            entry = next(
                e
                for e in reversed(table["entries"])
                if e["effective_date"] <= moment.date().isoformat()
            )
            civil = civil_jd(moment)
            if moment.year < 1972:
                offset = Fraction(str(entry["offset_seconds"])) + (
                    civil - Fraction(4800001, 2) - Fraction(str(entry["reference_mjd"]))
                ) * Fraction(str(entry["rate_seconds_per_day"]))
            else:
                offset = Fraction(entry["tai_minus_utc_seconds"])
            exact = civil + (offset + Fraction(32184, 1000)) / 86400
            proof["source"] = {
                **source,
                "method": "frozen_UTC_offset_and_rate",
                "entry": entry,
            }
        else:
            observed = native if replay else _historical_native(moment)
            if not isinstance(observed, dict) or set(observed) != {
                "utc_to_jd_arguments",
                "jd_tt",
                "jd_ut1",
                "delta_t_flag",
                "delta_t_days",
            }:
                raise ValueError("Missing historical UT1 ordering observation")
            if (
                observed["utc_to_jd_arguments"]
                != [
                    moment.year,
                    moment.month,
                    moment.day,
                    moment.hour,
                    moment.minute,
                    moment.second + moment.microsecond / 1e6,
                    1,
                ]
                or type(observed["delta_t_flag"]) is not int
                or observed["delta_t_flag"] != -1
            ):
                raise ValueError("Wrong historical native ordering path")
            delta = Fraction(_finite(observed["delta_t_days"]))
            ut1 = _finite(observed["jd_ut1"])
            if (
                _finite(observed["jd_tt"]) != physical_tt
                or ut1 + float(delta) != physical_tt
            ):
                raise ValueError("Historical ordering native epoch mismatch")
            _close(civil_jd(moment), ut1)
            exact = civil_jd(moment) + delta
            proof["source"] = {
                "method": "historical_UT1_plus_observed_native_Delta_T",
                "source_url": "https://www.astro.com/swisseph/swephprg.htm",
                "native_observation": observed,
            }
        _close(exact, physical_tt)
    proof["exact_jd_tt"] = {
        "numerator": str(exact.numerator),
        "denominator": str(exact.denominator),
    }
    return exact, proof


def reference_ordering(
    birth_label: str | None,
    birth_tt: float,
    reference_label: str,
    reference_tt: float,
    *,
    replay_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay is pure; only production may observe historical native Delta T."""

    def native(key: str) -> dict[str, Any] | None:
        if replay_proof is None:
            return None
        return cast(
            dict[str, Any] | None, replay_proof[key]["source"].get("native_observation")
        )

    birth, bp = _axis(
        birth_label, birth_tt, replay=replay_proof is not None, native=native("birth")
    )
    reference, rp = _axis(
        reference_label,
        reference_tt,
        replay=replay_proof is not None,
        native=native("reference"),
    )
    return {
        "method_id": METHOD,
        "birth": bp,
        "reference": rp,
        "relation": (
            "before" if reference < birth else "after" if reference > birth else "equal"
        ),
        "input_resolution_seconds": "0.000001",
        "native_execution_authenticated": False,
        "physical_accuracy_certified": False,
        "scope": SCOPE,
    }
