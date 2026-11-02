"""Lossless scalar witnesses for every evaluated Human Design interval sample.

Native execution, physical accuracy and historical clock realizations remain
unproven. Reconstruction uses supplied scalars, never another ephemeris call.
"""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime
from typing import Any

from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.human_design_birth_clock import resolve_birth_clock
from fatebridge.core.human_design_depth import cross_identifier
from fatebridge.core.human_design_mechanics import BODY_IDS, VALID_PROFILES, bodygraph
from fatebridge.core.human_design_native_positions import decode_native_positions
from fatebridge.core.human_design_variables import variables_from_activations

SIDES = ("personality", "design")
DIRECT_BODIES = (*BODY_IDS, "NorthNode")
METHOD_ID = "human_design_all_evaluated_sample_scalars_v2"
SCOPE = "本次实际求值的全部双时刻样本及各自数值设计根和实际设计端点见证；原生黄经／速度／返回旗标按direct_body_order排列，地球与南交点精确派生。不认证原生调用、星历物理精度、历史民用钟实现或连续区间穷尽。"


def pack_sample_witnesses(samples: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "method_id": METHOD_ID,
        "direct_body_order": list(DIRECT_BODIES),
        "native_scalar_order": ["longitude", "longitude_speed", "return_flags"],
        "samples": [
            {
                "birth_utc": chart["birth_utc"],
                "design_utc": chart["design_utc"],
                "time_scales": deepcopy(chart["time_scales"]),
                "design_solver": deepcopy(chart["design_solver"]),
                "native_positions": {
                    side: [
                        [
                            row[k]
                            for k in ("longitude", "longitude_speed", "return_flags")
                        ]
                        for row in chart["activations"][side]
                        if row["body"] in DIRECT_BODIES
                    ]
                    for side in SIDES
                },
            }
            for chart in samples
        ],
        "scope": SCOPE,
    }


def _clock(label: str | None, time: dict[str, Any]) -> None:
    required = {"jd_tt", "jd_ut1", "method", "future_leap_seconds_assumed_unchanged"}
    optional = {"utc_is_leap_second", "utc_label_status"}
    if not required <= set(time) or set(time) - required - optional:
        raise ValueError("Unexpected sample clock fields")
    if (
        any(
            type(time[k]) is not float or not math.isfinite(time[k])
            for k in ("jd_tt", "jd_ut1")
        )
        or type(time["method"]) is not str
    ):
        raise ValueError("Malformed sample time scalars")
    future = False
    is_leap = isinstance(label, str) and label[17:19] == "60"
    if label is None:
        if (
            time.get("utc_label_status")
            != "unrepresentable_historical_fractional_UTC_adjustment"
            or time["jd_tt"] >= 2441317.5 + (10 + 32.184) / 86400
        ):
            raise ValueError("Invalid missing historical UTC label")
    elif is_leap:
        anchor = datetime.fromisoformat(label[:17] + "59" + label[19:])
        offset = anchor.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("Sample label must use UTC")
        confirmed = resolve_birth_clock(
            birth_year=anchor.year,
            birth_month=anchor.month,
            birth_day=anchor.day,
            birth_hour=anchor.hour,
            birth_minute=anchor.minute,
            birth_second=60,
            birth_timezone="UTC",
        )
        assert confirmed.jd_tt is not None
        expected = confirmed.jd_tt + (anchor.microsecond / 1e6) / 86400
        if abs(time["jd_tt"] - expected) * 86400 > 0.0002:
            raise ValueError("Inserted-second label detached from frozen TT")
    else:
        moment = datetime.fromisoformat(label)
        offset = moment.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("Sample label must use UTC")
        future = moment >= datetime.fromisoformat(leap_table()["expires_at"])
        if moment.year >= 1972:
            rows = [
                r
                for r in leap_table()["entries"]
                if r["effective_date"] <= moment.date().isoformat()
            ]
            expected = (
                _julian_day(moment)
                + (rows[-1]["tai_minus_utc_seconds"] + 32.184) / 86400
            )
            if abs(time["jd_tt"] - expected) * 86400 > 0.0002:
                raise ValueError("Modern UTC label detached from frozen TT")
    if (
        type(time["future_leap_seconds_assumed_unchanged"]) is not bool
        or time["future_leap_seconds_assumed_unchanged"] != future
    ):
        raise ValueError("Sample future leap assumption contradicts its label")
    if "utc_is_leap_second" in time and (
        type(time["utc_is_leap_second"]) is not bool
        or time["utc_is_leap_second"] != is_leap
    ):
        raise ValueError("Sample inserted-second flag contradicts its label")
    expected_status = (
        "unrepresentable_historical_fractional_UTC_adjustment"
        if label is None
        else "inserted_UTC_leap_second" if is_leap else "unique_civil_label"
    )
    if "utc_label_status" in time and time["utc_label_status"] != expected_status:
        raise ValueError("Sample label status contradicts its label")


def unpack_sample_witnesses(
    witness: dict[str, Any],
    node_mode: str,
    *,
    require_swiss_files: bool,
    physical_backend_policy: str,
) -> dict[float, dict[str, Any]]:
    if (
        set(witness)
        != {"method_id", "direct_body_order", "native_scalar_order", "samples", "scope"}
        or witness["method_id"] != METHOD_ID
        or witness["scope"] != SCOPE
        or witness["direct_body_order"] != list(DIRECT_BODIES)
        or witness["native_scalar_order"]
        != ["longitude", "longitude_speed", "return_flags"]
    ):
        raise ValueError("Invalid interval witness layout or scope")
    if node_mode not in {"true", "mean"} or physical_backend_policy not in {
        "auto",
        "strict_jpl",
    }:
        raise ValueError("Invalid interval source policy")
    charts: dict[float, dict[str, Any]] = {}
    graph_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    for sample in witness["samples"]:
        if (
            set(sample)
            != {
                "birth_utc",
                "design_utc",
                "time_scales",
                "native_positions",
                "design_solver",
            }
            or set(sample["time_scales"]) != set(SIDES)
            or set(sample["native_positions"]) != set(SIDES)
        ):
            raise ValueError("Invalid sample fields")
        sides = {}
        for side in SIDES:
            _clock(
                sample["birth_utc"] if side == "personality" else sample["design_utc"],
                sample["time_scales"][side],
            )
            rows = decode_native_positions(
                sample["native_positions"][side],
                node_mode,
                require_swiss_files=require_swiss_files,
                physical_backend_policy=physical_backend_policy,
            )
            sides[side] = rows
        suns = {
            side: next(r for r in rows if r["body"] == "Sun")
            for side, rows in sides.items()
        }
        profile = f"{suns['personality']['line']}/{suns['design']['line']}"
        if (
            profile not in VALID_PROFILES
            or abs(
                (suns["personality"]["longitude"] - suns["design"]["longitude"]) % 360
                - 88
            )
            > 1e-7
        ):
            raise ValueError("Invalid sample solar/profile relationship")
        birth = sample["time_scales"]["personality"]["jd_tt"]
        design = sample["time_scales"]["design"]["jd_tt"]
        if not 70 < birth - design < 110 or (
            charts and birth <= next(reversed(charts))
        ):
            raise ValueError("Unsorted, duplicate or invalid sample epochs")
        keys = tuple(tuple(sorted({r["gate"] for r in sides[s]})) for s in SIDES)
        if keys not in graph_cache:
            graph_cache[keys] = bodygraph(keys[0], keys[1])
        angle = (
            "juxtaposition"
            if profile == "4/1"
            else "right" if suns["personality"]["line"] <= 4 else "left"
        )
        quartet = [
            next(r["gate"] for r in sides[s] if r["body"] == b)
            for s, b in (
                ("personality", "Sun"),
                ("personality", "Earth"),
                ("design", "Sun"),
                ("design", "Earth"),
            )
        ]
        charts[birth] = {
            "birth_utc": sample["birth_utc"],
            "design_utc": sample["design_utc"],
            "time_scales": sample["time_scales"],
            "design_solver": sample["design_solver"],
            "activations": sides,
            "variables": variables_from_activations(sides),
            "bodygraph": graph_cache[keys],
            "profile": profile,
            "incarnation_cross": {
                "gates": quartet,
                "order": [
                    "personality_sun",
                    "personality_earth",
                    "design_sun",
                    "design_earth",
                ],
                "angle": angle,
                **cross_identifier(quartet[0], angle),
            },
        }
        from fatebridge.validation.human_design_solar_root import (
            verify_solar_root_context,
        )

        if verify_solar_root_context(
            {
                **charts[birth],
                "calculation_policy": {
                    "node_mode": node_mode,
                    "require_swiss_files": require_swiss_files,
                    "physical_backend_policy": physical_backend_policy,
                },
            }
        )["errors"]:
            raise ValueError("Invalid sample root or actual design endpoint witnesses")
    return charts
