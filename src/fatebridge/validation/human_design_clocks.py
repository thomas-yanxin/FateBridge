"""Pure replay of observed time conversions; never call the native producer."""

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fatebridge.core.astro.historical_utc import (
    HistoricalUTCAdjustment,
    historical_tai_minus_utc,
    historical_utc_from_tt,
)
from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.human_design_birth_clock import resolve_birth_clock
from fatebridge.core.human_design_clock_observation import INPUT_KEYS, METHOD, SCOPE
from fatebridge.core.human_design_reference_clock import (
    LEAP_REFERENCE,
    reference_datetime,
)
from fatebridge.core.human_design_reference_order import validate_reference_precision
from fatebridge.utils.timezones import timezone_rules_metadata
from fatebridge.validation.claims import _same_value

TOLERANCE_SECONDS = 0.0002
CONTINUOUS = "continuous_TT_interval_sample"
DESIGN = "continuous_TT_root_with_frozen_UTC_leap_policy"


def _finite(value: Any) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("Clock requires a finite binary64 JD or Delta T")
    return value


def _utc(label: str) -> datetime:
    moment = datetime.fromisoformat(label)
    if moment.utcoffset() != timedelta(0) or label not in {
        moment.isoformat(),
        moment.isoformat(timespec="microseconds"),
    }:
        raise ValueError("Clock label must be normalized aware UTC")
    return moment


def _civil_tt(moment: datetime) -> float | None:
    civil = _julian_day(moment)
    offset = historical_tai_minus_utc(moment)
    if offset is None:
        if moment.year < 1972:
            return None
        offset = next(
            e["tai_minus_utc_seconds"]
            for e in reversed(leap_table()["entries"])
            if e["effective_date"] <= moment.date().isoformat()
        )
    return civil + (offset + 32.184) / 86400


def _civil_method(moment: datetime) -> str:
    if moment.year < 1960:
        return "pre_1972_swiss_UT1_delta_t"
    if moment.year == 1960:
        return "SOFA_1960_UTC_drift_to_TT_swiss_delta_t_to_UT1"
    if moment.year < 1972:
        return "IERS_1961_1971_UTC_drift_to_TT_swiss_delta_t_to_UT1"
    return "IERS_UTC_to_TT_swiss_delta_t_to_UT1"


def _leap_tt(label: str) -> float:
    anchor = _utc(label[:17] + "59" + label[19:])
    clock = resolve_birth_clock(
        birth_year=anchor.year,
        birth_month=anchor.month,
        birth_day=anchor.day,
        birth_hour=anchor.hour,
        birth_minute=anchor.minute,
        birth_second=60,
        birth_timezone="UTC",
    )
    assert clock.jd_tt is not None
    return clock.jd_tt + (anchor.microsecond / 1e6) / 86400


def _close(a: float, b: float) -> None:
    if abs(a - b) * 86400 > TOLERANCE_SECONDS:
        raise ValueError("Civil label is detached from physical epoch")


class ClockReplay:
    def __init__(self, payload: dict[str, Any]):
        proof = payload["clock_evidence"]
        expected_keys = {
            "method_id",
            "input",
            "cycle_reference_datetime",
            "timezone_rules",
            "conversions",
            "native_execution_authenticated",
            "measured_UT1_certified",
            "physical_accuracy_certified",
            "scope",
        }
        if proof.get("compare_cycle_origins") is True:
            expected_keys.add("compare_cycle_origins")
        if (
            set(proof) != expected_keys
            or proof["method_id"] != METHOD
            or proof["scope"] != SCOPE
            or any(
                proof[k] is not False
                for k in (
                    "native_execution_authenticated",
                    "measured_UT1_certified",
                    "physical_accuracy_certified",
                )
            )
            or set(proof["input"]) != set(INPUT_KEYS)
        ):
            raise ValueError("Malformed or falsely certified clock evidence")
        self.civil: dict[tuple[str, float, float], dict[str, Any]] = {}
        self.inverse: dict[tuple[float, float], dict[str, Any]] = {}
        self.displays: dict[float, dict[str, Any]] = {}
        events = proof["conversions"]
        if not isinstance(events, list) or not events:
            raise ValueError("Missing conversion observations")
        for event in events:
            kind = event["kind"]
            tt = _finite(event["jd_tt"])
            if kind == "tt_to_utc_display":
                if set(event) != {"kind", "jd_tt", "utc_label", "utc_is_leap_second"}:
                    raise ValueError("Unexpected display observation")
                if tt in self.displays:
                    raise ValueError("Duplicate display observation")
                self.displays[tt] = event
                continue
            ut1 = _finite(event["jd_ut1"])
            if kind == "civil_to_tt_ut1":
                if set(event) != {
                    "kind",
                    "utc_label",
                    "jd_civil",
                    "jd_tt",
                    "jd_ut1",
                    "steps",
                    "native_utc_to_jd",
                }:
                    raise ValueError("Unexpected civil observation")
                moment = _utc(event["utc_label"])
                civil = _finite(event["jd_civil"])
                if civil != _julian_day(moment):
                    raise ValueError("Wrong proleptic Gregorian civil JD")
                expected = _civil_tt(moment)
                if expected is None:
                    # Swiss historically interprets these UTC-named inputs as
                    # UT1. The returned TT is an opaque native observation.
                    if (
                        event["native_utc_to_jd"]
                        != [
                            moment.year,
                            moment.month,
                            moment.day,
                            moment.hour,
                            moment.minute,
                            moment.second + moment.microsecond / 1e6,
                            1,
                        ]
                        or event["steps"] != []
                    ):
                        raise ValueError("Wrong historical native calendar arguments")
                    _close(ut1, civil)
                else:
                    if tt != expected or event["native_utc_to_jd"] is not None:
                        raise ValueError("Wrong frozen UTC offset conversion")
                    self._steps(event, civil, civil_forward=True)
                key = event["utc_label"], tt, ut1
                if key in self.civil:
                    raise ValueError("Duplicate civil observation")
                self.civil[key] = event
            elif kind == "tt_to_ut1":
                if set(event) != {"kind", "jd_tt", "jd_ut1", "steps"}:
                    raise ValueError("Unexpected inverse observation")
                self._steps(event, tt, civil_forward=False)
                if (tt, ut1) in self.inverse:
                    raise ValueError("Duplicate inverse observation")
                self.inverse[tt, ut1] = event
            else:
                raise ValueError("Unknown clock conversion")
        for tt, display in self.displays.items():
            label = display["utc_label"]
            leap = isinstance(label, str) and label[17:19] == "60"
            if display["utc_is_leap_second"] is not leap:
                raise ValueError("Wrong display leap flag")
            self.check_label(label, tt)
        clock = resolve_birth_clock(**proof["input"])
        self.birth_clock = clock
        policy = payload["calculation_policy"]
        if (
            proof["timezone_rules"]
            != timezone_rules_metadata(proof["input"]["birth_timezone"])
            or policy["birth_local"] != clock.local_label
            or policy["birth_timezone"] != proof["input"]["birth_timezone"]
            or policy["calendar"] != "proleptic_gregorian"
            or policy["solar_clock_rebasing"] is not False
            or payload["birth_utc"] != clock.utc_label
        ):
            raise ValueError("Birth input, timezone rules and calendar policy disagree")
        if (
            clock.leap_second
            and payload["time_scales"]["personality"]["jd_tt"] != clock.jd_tt
        ):
            raise ValueError("Birth leap second TT mismatch")

    @staticmethod
    def _steps(event: dict[str, Any], initial: float, *, civil_forward: bool) -> None:
        steps = event["steps"]
        if not isinstance(steps, list) or len(steps) != 4:
            raise ValueError("Exactly four original Delta T iterations required")
        current = initial
        for row in steps:
            if not isinstance(row, list) or len(row) != 3:
                raise ValueError("Malformed Delta T step")
            at, flag, delta = row
            if (
                _finite(at) != current
                or type(flag) is not int
                or flag != (2 if civil_forward or current >= 2436934.5 else -1)
            ):
                raise ValueError("Delta T input or actual flag mismatch")
            current = event["jd_tt"] - _finite(delta)
        if current != event["jd_ut1"]:
            raise ValueError("Delta T output mismatch")

    def check_label(
        self, label: str | None, tt: float, ut1: float | None = None
    ) -> None:
        if label is None:
            try:
                historical_utc_from_tt(tt)
            except HistoricalUTCAdjustment:
                return
            raise ValueError("Missing label outside a historical UTC adjustment")
        if label[17:19] == "60":
            _close(tt, _leap_tt(label))
            return
        moment = _utc(label)
        expected = _civil_tt(moment)
        if expected is not None:
            _close(tt, expected)
        else:
            # The historical UTC-named display is modeled UT1, not modern UTC.
            options = [u for t, u in self.inverse if t == tt]
            options.extend(u for _, t, u in self.civil if t == tt)
            if ut1 is not None:
                options = [ut1]
            if not options or not any(
                abs(u - _julian_day(moment)) * 86400 <= TOLERANCE_SECONDS
                for u in options
            ):
                raise ValueError("Historical civil label disagrees with observed UT1")

    def label_context(self, tt: float) -> dict[str, Any]:
        display = self.displays[tt]
        label = display["utc_label"]
        return {
            "utc_label": label,
            "utc_label_status": (
                "inserted_UTC_leap_second"
                if display["utc_is_leap_second"]
                else (
                    "unique_civil_label"
                    if label is not None
                    else "unrepresentable_historical_fractional_UTC_adjustment"
                )
            ),
            "future_leap_seconds_assumed_unchanged": bool(
                label is not None
                and label[17:19] != "60"
                and _utc(label) >= datetime.fromisoformat(leap_table()["expires_at"])
            ),
        }

    def check_time(self, label: str | None, time: dict[str, Any], method: str) -> None:
        tt, ut1 = _finite(time["jd_tt"]), _finite(time["jd_ut1"])
        self.check_label(label, tt, ut1)
        if time["method"] != method:
            raise ValueError("Clock method does not describe its actual conversion")
        if method in {
            CONTINUOUS,
            DESIGN,
            "human_design_confirmed_birth_leap_second_v1",
        }:
            if (tt, ut1) not in self.inverse:
                raise ValueError("Returned inverse clock lacks its conversion witness")
            if method == "human_design_confirmed_birth_leap_second_v1":
                # The exact declared input and the binary64 inverse display
                # need not have the same label at a leap-second alias.
                clock = self.birth_clock
                if not clock.leap_second or (label, tt) != (
                    clock.utc_label,
                    clock.jd_tt,
                ):
                    raise ValueError(
                        "Leap input label or selected TT detached from input"
                    )
                context = {
                    "utc_label": clock.utc_label,
                    "utc_label_status": "inserted_UTC_leap_second",
                    "future_leap_seconds_assumed_unchanged": False,
                }
            else:
                context = self.label_context(tt)
            expected = {
                "jd_tt": tt,
                "jd_ut1": ut1,
                "method": method,
                "future_leap_seconds_assumed_unchanged": context[
                    "future_leap_seconds_assumed_unchanged"
                ],
                "utc_is_leap_second": context["utc_label_status"]
                == "inserted_UTC_leap_second",
                "utc_label_status": context["utc_label_status"],
            }
            if context["utc_label"] != label:
                raise ValueError("Returned display lacks its actual witness")
        else:
            if label is None:
                raise ValueError("Civil conversion requires a label")
            if (label, tt, ut1) not in self.civil:
                raise ValueError("Returned civil clock lacks its conversion witness")
            expected = {
                "jd_tt": tt,
                "jd_ut1": ut1,
                "method": method,
                "future_leap_seconds_assumed_unchanged": _utc(label)
                >= datetime.fromisoformat(leap_table()["expires_at"]),
            }
        if not _same_value(time, expected):
            raise ValueError("Clock flags or fields do not match their conversion")

    def reference_epoch(self, value: str) -> tuple[str, float]:
        validate_reference_precision(value)
        if LEAP_REFERENCE.fullmatch(value) is not None:
            # Normalize an explicit offset with the same pure leap-label policy.
            anchor = datetime.fromisoformat(
                value[:17] + "59" + value[19:].replace("Z", "+00:00")
            )
            offset = anchor.utcoffset()
            if offset is None:
                raise ValueError("Cycle leap reference must be aware")
            clock = resolve_birth_clock(
                birth_year=anchor.year,
                birth_month=anchor.month,
                birth_day=anchor.day,
                birth_hour=anchor.hour,
                birth_minute=anchor.minute,
                birth_second=60,
                birth_timezone=str(offset.total_seconds() / 3600),
            )
            assert clock.jd_tt is not None
            label = clock.utc_label[:20] + f"{anchor.microsecond:06d}+00:00"
            return label, clock.jd_tt + (anchor.microsecond / 1e6) / 86400
        moment = reference_datetime(value)
        if moment.utcoffset() is None:
            raise ValueError("Cycle reference must be aware")
        moment = moment.astimezone(timezone.utc)
        if not 1800 <= moment.year <= 2600:
            raise ValueError("Cycle reference out of range")
        matches = {tt for label, tt, _ in self.civil if label == moment.isoformat()}
        if len(matches) != 1:
            raise ValueError("Cycle reference lacks an unambiguous conversion")
        return moment.isoformat(), matches.pop()


def verify_clock_records(payload: dict[str, Any]) -> ClockReplay:
    replay = ClockReplay(payload)
    main_method = (
        "human_design_confirmed_birth_leap_second_v1"
        if payload.get("birth_clock_evidence") is not None
        else _civil_method(_utc(payload["birth_utc"]))
    )
    nominal_tt = payload["time_scales"]["personality"]["jd_tt"]

    def walk(value: Any, path: str = "") -> None:
        if isinstance(value, dict):
            if "time_scales" in value and {"birth_utc", "design_utc"} <= set(value):
                times = value["time_scales"]
                nominal = value is payload or (
                    "evaluation_witnesses" in path
                    and times["personality"]["jd_tt"] == nominal_tt
                )
                replay.check_time(
                    value["birth_utc"],
                    times["personality"],
                    main_method if nominal else CONTINUOUS,
                )
                replay.check_time(value["design_utc"], times["design"], DESIGN)
            for key, child in value.items():
                if key not in {
                    "clock_evidence",
                    "interpretation",
                    "rule_trace",
                    "run_metadata",
                }:
                    walk(child, path + "." + key)
        elif isinstance(value, list):
            for child in value:
                walk(child, path)

    walk(payload)
    context = payload["cycle_context"]
    reference = payload["clock_evidence"]["cycle_reference_datetime"]
    if context["status"] == "not_requested":
        if reference is not None:
            raise ValueError("Missing requested cycle clock")
    else:
        label, tt = replay.reference_epoch(reference)
        if (context["reference_utc"], context["reference_jd_tt"]) != (label, tt):
            raise ValueError("Cycle reference detached from input")
        for body in context["bodies"]:
            for event in body["contacts"]:
                expected = replay.label_context(event["jd_tt"])
                if any(not _same_value(event.get(k), v) for k, v in expected.items()):
                    raise ValueError(
                        "Cycle contact display contradicts its clock witness"
                    )
    return replay
