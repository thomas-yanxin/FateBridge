"""An integrity failure is not an undefined optional astronomical quantity."""

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from fatebridge.core.astro import (
    classical,
    ephemeris,
    geometry,
    layout,
    physical_epoch,
    runtime,
)
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.profiles import (
    _resolve_relative_house_system,
    _resolve_relative_zodiacal_mode,
)
from fatebridge.utils.errors import EphemerisSourceError

FIXTURE = Path(__file__).parent / "fixtures/western-source-errors-v1"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())


def inject(target, error, monkeypatch):
    """Inject at the affected helper's actual dependency, not its output."""

    def broken(*args, **kwargs):
        raise error

    if target == "extended_utc_display":
        original = physical_epoch.datetime_from_tt

        def display(jd_tt):
            if jd_tt < 1721425.5:
                raise error
            return original(jd_tt)

        monkeypatch.setattr(physical_epoch, "datetime_from_tt", display)
    elif target == "planetary_hour_calendar":
        monkeypatch.setattr(classical, "datetime_from_ut1", broken)
    elif target == "legacy_ayanamsha":
        monkeypatch.setattr(geometry, "native_lahiri_ayanamsha", broken)
    elif target == "sidereal_house_layout":
        monkeypatch.setattr(layout, "native_lahiri_houses", broken)
    else:
        original = runtime.ephemeris_call

        def call(operation, *args, **kwargs):
            caller = inspect.currentframe().f_back.f_code.co_name
            selected = (
                (target == "native_angles" and caller == "_swisseph_angles")
                or (target == "sun_event" and caller == "_sun_event")
                or (
                    target == "tropical_house_layout"
                    and caller == "_relative_house_layout"
                )
                or (
                    target == "classical_obliquity"
                    and caller == "_build_classical_layer"
                    and operation == "calc_ut"
                )
            )
            if selected:
                raise error
            return original(operation, *args, **kwargs)

        monkeypatch.setattr(runtime, "ephemeris_call", call)


def invoke(target):
    jd = 2461045.0
    if target == "extended_utc_display":
        return physical_epoch.utc_from_tt(PROTOCOL["extended_event_jd_tt"])
    if target == "native_angles":
        return ephemeris._swisseph_angles(jd, 0, 40)
    if target == "sun_event":
        return classical._sun_event(jd, 0, 40, True)
    if target == "planetary_hour_calendar":
        return classical._planetary_hours(jd, 0, 40, "UTC")
    if target == "classical_obliquity":
        return classical._build_classical_layer(
            [], [], 0, chart_sect="day", julian_day=jd
        )
    if target == "legacy_ayanamsha":
        return geometry._ayanamsha(jd)
    birth = build_astro_birth_info(
        birth_year=2026,
        birth_month=1,
        birth_day=4,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
    )
    return layout._relative_house_layout(
        birth,
        house_system_info=_resolve_relative_house_system(3),
        zodiacal_info=_resolve_relative_zodiacal_mode(
            int(target == "sidereal_house_layout")
        ),
    )


def test_protocol_and_before_reference_remain_sealed():
    seal = json.loads((FIXTURE / "seal.json").read_text())
    for name, digest in seal["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert len(PROTOCOL["targets"]) == 8


@pytest.mark.parametrize("target", PROTOCOL["targets"])
@pytest.mark.parametrize("reason", PROTOCOL["source_error_reasons"])
def test_integrity_failure_preserves_type_reason_and_identity(
    target, reason, monkeypatch
):
    failure = EphemerisSourceError(reason)
    inject(target, failure, monkeypatch)
    with pytest.raises(EphemerisSourceError) as caught:
        invoke(target)
    assert caught.value is failure


@pytest.mark.parametrize("target", PROTOCOL["targets"])
def test_ordinary_failure_retains_its_existing_optional_or_domain_behavior(
    target, monkeypatch
):
    inject(target, ValueError("ordinary unavailable quantity"), monkeypatch)
    if target in {"tropical_house_layout", "sidereal_house_layout"}:
        with pytest.raises(ValueError) as caught:
            invoke(target)
        assert not isinstance(caught.value, EphemerisSourceError)
    else:
        result = invoke(target)
        if target == "extended_utc_display":
            assert result[0].startswith("0000-") and result[1:] == (None, False)
        elif target == "classical_obliquity":
            assert result["obliquity"] is None
        elif target == "legacy_ayanamsha":
            assert result == 23.853 + (2461045.0 - 2451545.0) / 36525.0 * 1.3971
        else:
            assert result is None
