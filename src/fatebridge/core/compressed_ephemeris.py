"""Repair witnessed Swiss compressed-file endpoints before returning a state.

Swiss 2.10.03 retains a file at its inclusive final epoch. That context can
return an erroneous state. Select the adjacent context from its header alone,
then recalculate the *original* operation and arguments. This is not an epoch
shift, a new ephemeris, a universal cache normalization or an accuracy proof.
The caller must hold the shared native-runtime lock throughout.
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable, Iterator

from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.utils.errors import EphemerisSourceError

POLICY_ID = "compressed_file_endpoint_context_v5"
SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c#L2163-L2179"
_AUDIT: ContextVar[dict[str, Any] | None] = ContextVar(
    "compressed_endpoint_audit", default=None
)
_LAST_COORDINATE: ContextVar[dict[str, Any] | None] = ContextVar(
    "compressed_last_coordinate_context", default=None
)
_DEPENDENCY_CONTEXT: ContextVar[float | None] = ContextVar(
    "compressed_native_dependency_context", default=None
)
_DEPENDENCY_RECEPTION: ContextVar[dict[str, Any] | None] = ContextVar(
    "compressed_native_dependency_reception", default=None
)
_OBSERVER_SAMPLE: ContextVar[float | None] = ContextVar(
    "compressed_geometric_observer_sample", default=None
)


@contextmanager
def preserve_native_observer_sample_context(
    reception_tt: float, sample_tt: float, model: str, *, native: Any
) -> Iterator[None]:
    """Sample only geometric barycentric Earth in the checked center files.

    Unlike a retarded dependency, an acceleration sample may be in the future.
    Every nonzero sample must be strictly inside the already selected windows.
    This never permits apparent Moon/planet calls at another reception epoch.
    The caller owns the native lock and verifies exact center restoration.
    """
    if not all(math.isfinite(t) for t in (reception_tt, sample_tt)) or model not in {
        "swieph",
        "jpl",
    }:
        raise EphemerisSourceError("observer_source_window_incoherent")
    before = _windows(native) if model == "swieph" else None
    reception = _LAST_COORDINATE.get() or _DEPENDENCY_RECEPTION.get()
    if model == "swieph":
        pad = 64 * math.ulp(sample_tt)
        if (
            before is None
            or not _valid(before)
            or not all(
                w[1] <= reception_tt <= w[2] and w[1] + pad < sample_tt < w[2] - pad
                for w in before
            )
            or _AUDIT.get() is not None
            and (
                reception is None
                or not reception.get("private_native_cache_reset")
                or reception.get("physical_jd_tt") != reception_tt
                or reception.get("selected_windows") != _public_windows(before)
            )
        ):
            raise EphemerisSourceError("observer_source_window_incoherent")
    sample_token = _OBSERVER_SAMPLE.set(sample_tt)
    dependency_token = _DEPENDENCY_CONTEXT.set(sample_tt) if model == "swieph" else None
    reception_token = _DEPENDENCY_RECEPTION.set(reception)
    try:
        yield
        if model == "swieph" and _windows(native) != before:
            raise EphemerisSourceError("observer_source_window_incoherent")
    finally:
        _DEPENDENCY_RECEPTION.reset(reception_token)
        if dependency_token is not None:
            _DEPENDENCY_CONTEXT.reset(dependency_token)
        _OBSERVER_SAMPLE.reset(sample_token)


@contextmanager
def preserve_native_dependency_context(
    reception_tt: float, sample_tt: float, model: str, *, native: Any
) -> Iterator[None]:
    """Retain an already selected source for one checked retarded dependency.

    This does not bypass the source guard. Both epochs must fit the observed
    windows, which must stay identical through the dependent call. Use only
    under the native lock after the reception state was freshly established.
    """
    if _AUDIT.get() is None or model != "swieph":
        yield
        return
    before = _windows(native)
    reception = _LAST_COORDINATE.get()
    if reception is None and _DEPENDENCY_CONTEXT.get() is not None:
        reception = _DEPENDENCY_RECEPTION.get()
    if (
        not math.isfinite(reception_tt)
        or not math.isfinite(sample_tt)
        or before is None
        or not _valid(before)
        or not all(w[1] <= sample_tt <= reception_tt <= w[2] for w in before)
        or reception is None
        or not reception.get("private_native_cache_reset")
        or reception.get("physical_jd_tt") != reception_tt
        or reception.get("selected_windows") != _public_windows(before)
    ):
        raise EphemerisSourceError("dependency_source_window_incoherent")
    token = _DEPENDENCY_CONTEXT.set(sample_tt)
    reception_token = _DEPENDENCY_RECEPTION.set(reception)
    try:
        yield
        if _windows(native) != before:
            raise EphemerisSourceError("dependency_source_window_incoherent")
    finally:
        _DEPENDENCY_RECEPTION.reset(reception_token)
        _DEPENDENCY_CONTEXT.reset(token)


@contextmanager
def audit_compressed_endpoints() -> Iterator[None]:
    """Keep bounded diagnostics for one private calculation, including repeats."""
    if _AUDIT.get() is not None:
        yield
        return
    token = _AUDIT.set(
        {"calls": 0, "changed": 0, "records": {}, "omitted": 0, "resets": 0}
    )
    coordinate_token = _LAST_COORDINATE.set(None)
    try:
        yield
    finally:
        _AUDIT.reset(token)
        _LAST_COORDINATE.reset(coordinate_token)
        # The private calls changed native caches. A receipt from before this
        # outer audit cannot describe their current state and must not leak.
        _LAST_COORDINATE.set(None)


def endpoint_context_evidence() -> dict[str, Any]:
    audit = _AUDIT.get()
    return {
        "policy_id": POLICY_ID,
        "trigger": "owned_physical_light_path_or_observed_compressed_endpoint",
        "endpoint_guard_trigger": "actual_SWIEPH_physical_calc_at_observed_file_end_within_64_TT_ULPs",
        "input_instant_shifted": False,
        "native_coordinates_may_be_corrected": True,
        "context_strategy": (
            "fresh_owned_native_context_before_each_physical_coordinate"
            if audit is not None
            else "external_endpoint_guard_and_geocentric_solar_dependency_rebuild"
        ),
        "native_cache_resets_so_far": audit["resets"] if audit else None,
        "reference_preflight": "same_reception_epoch_geometric_Sun",
        "calls_corrected_so_far": audit["calls"] if audit else None,
        "native_states_changed_so_far": audit["changed"] if audit else None,
        "records": list(audit["records"].values()) if audit else [],
        "unrecorded_calls_at_record_limit": audit["omitted"] if audit else 0,
        "source_url": SOURCE_URL,
        "scope": "Within the owned private operation, reset computed native state using the same path and preselect with a same-reception-epoch geometric Sun. For supported geocentric apparent Sun/Moon/planet requests, establish the checked reception/retarded light-path context before the exact original coordinate call. Native owned default model/tidal settings are reapplied; sidereal/topocentric parameters and fixed Delta-T survive set_ephe_path. Outside that operation, supported Swiss geocentric apparent Sun calls rebuild reception dependencies in their checked common source windows without resetting caller configuration; other calls retain the post-call endpoint guard. Correction counts describe preflight or requested native subcalls, not independent samples or proof that an unevaluated original target changed. No atomic read-set or physical accuracy certificate.",
    }


def _windows(native: Any) -> tuple[tuple[Any, ...], ...] | None:
    getter = getattr(native, "get_current_file_data", None)
    if not callable(getter):
        return None
    return tuple(tuple(getter(slot)) for slot in (0, 1))


def _valid(windows: tuple[tuple[Any, ...], ...]) -> bool:
    return all(
        len(w) == 4
        and w[0]
        and math.isfinite(w[1])
        and math.isfinite(w[2])
        and w[1] < w[2]
        for w in windows
    )


def _public_windows(windows: tuple[tuple[Any, ...], ...]) -> list[dict[str, Any]]:
    return [
        dict(
            slot=slot,
            filename=Path(w[0]).name,
            start_jd_tt=float(w[1]),
            end_jd_tt=float(w[2]),
            de_number=int(w[3]),
        )
        for slot, w in enumerate(windows)
    ]


def _is_swiss(native: Any, result: Any) -> bool:
    return bool(
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[1], int)
        and result[1] >= 0
        and result[1] & _model_mask(native) == native.FLG_SWIEPH
    )


def _model_mask(native: Any) -> int:
    return int(native.FLG_SWIEPH | native.FLG_MOSEPH | native.FLG_JPLEPH)


def _physical_slots(native: Any, body: int, flags: int) -> tuple[int, ...]:
    """Use the effective native origin, not a possibly overridden request."""
    helio = getattr(native, "FLG_HELCTR", 8)
    bary = getattr(native, "FLG_BARYCTR", 16384)
    origin = flags & (helio | bary)
    if body == 14 and not origin or body == 0 and origin == helio:
        return ()  # Native reference identities, not physical vectors.
    if body in {1, 14} or not origin:
        return (0, 1)
    return (0,)


def _physical_windows(
    native: Any, body: int, flags: int
) -> tuple[tuple[Any, ...], ...] | None:
    slots = _physical_slots(native, body, flags)
    if not slots:
        return ()
    observed = _windows(native)
    return None if observed is None else tuple(observed[slot] for slot in slots)


def _require_observer_windows(
    native: Any,
    body: int,
    flags: int,
    epoch: float,
    windows: tuple[tuple[Any, ...], ...],
) -> None:
    """SWIEPH can hide a Moshier Moon used to turn EMB into Earth.

    sweplan() in the inspected native version explicitly permits that mixed
    dependency without clearing the top-level SWIEPH bit. Do not relabel the
    mixture as pure Moshier or supply an invented Moon position. Geocentric
    physical observations require both native contexts; independent origins
    retain their existing semantics. This is not an atomic read-set proof.
    """
    slots = _physical_slots(native, body, flags)
    if not slots:
        return
    if (
        str(getattr(native, "version", "unavailable")),
        binding_distribution_version(native, version),
    ) != ("2.10.03", "2.10.3.2"):
        return
    if (
        len(windows) != len(slots)
        or not _valid(windows)
        or not all(w[1] <= epoch <= w[2] for w in windows)
    ):
        raise EphemerisSourceError("swiss_dependency_unavailable")


def _post_call_endpoint_guard(
    native: Any,
    operation: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    invoke: Callable[[Any, str, tuple[Any, ...], dict[str, Any]], Any],
) -> Any:
    """Preserve ordinary returns exactly; never substitute an anchor's state."""
    result = invoke(native, operation, args, kwargs)
    if operation not in {"calc", "calc_ut"}:
        return result
    body = args[1] if len(args) > 1 else kwargs.get("planet")
    # Physical Sun through Pluto and Earth. Analytical nodes/fictitious factors
    # can leave unrelated file slots populated and must not trigger this rule.
    if (
        not isinstance(body, int)
        or body not in {*range(10), 14}
        or not _is_swiss(native, result)
    ):
        return result
    instant = (
        args[0] if args else kwargs.get("tjdet" if operation == "calc" else "tjdut")
    )
    if instant is None or not math.isfinite(instant):
        return result
    flags = (
        args[2]
        if len(args) > 2
        else kwargs.get("flags", native.FLG_SWIEPH | native.FLG_SPEED)
    )
    epoch = float(instant)
    if operation == "calc_ut":
        epoch += native.deltat_ex(epoch, result[1] & _model_mask(native))
    initial = _physical_windows(native, body, result[1])
    if initial is None:
        return result
    pad = 64 * math.ulp(epoch)
    ends = [w[2] for w in initial if len(w) == 4 and w[0] and abs(epoch - w[2]) <= pad]
    if not ends:
        _require_observer_windows(native, body, result[1], epoch, initial)
        return result
    if not _valid(initial):
        raise EphemerisSourceError("compressed_endpoint_unresolved")
    if (
        str(getattr(native, "version", "unavailable")),
        binding_distribution_version(native, version),
    ) != ("2.10.03", "2.10.3.2"):
        raise EphemerisSourceError("compressed_endpoint_unverified")
    original = result
    anchors: list[float] = []
    for _ in range(5):
        anchor = max(ends) + 128 * math.ulp(epoch)
        if not math.isfinite(anchor) or anchor in anchors or anchor <= max(ends):
            raise EphemerisSourceError("compressed_endpoint_unresolved")
        anchors.append(anchor)
        try:
            # The anchor is always TT, even when the requested operation is UT.
            primed = invoke(native, "calc", (anchor, body, flags), {})
            if not _is_swiss(native, primed):
                raise EphemerisSourceError("model_changed")
            result = invoke(native, operation, args, kwargs)
        except EphemerisSourceError:
            raise
        except Exception as error:
            raise EphemerisSourceError("compressed_endpoint_unresolved") from error
        if not _is_swiss(native, result):
            raise EphemerisSourceError("model_changed")
        if result[1] != original[1]:
            raise EphemerisSourceError("coordinate_contract_changed")
        selected = _physical_windows(native, body, result[1])
        if selected is None or not _valid(selected):
            raise EphemerisSourceError("compressed_endpoint_unresolved")
        if [w[3] for w in selected] != [w[3] for w in initial]:
            raise EphemerisSourceError("edition_changed")
        if all(w[1] + pad < epoch < w[2] - pad for w in selected):
            _require_observer_windows(native, body, result[1], epoch, selected)
            if len(result[0]) != 6 or not all(math.isfinite(x) for x in result[0]):
                raise EphemerisSourceError("coordinate_values_unavailable")
            # calc_ut's TT mapping must survive the context selection too.
            if operation == "calc_ut" and (
                float(instant)
                + native.deltat_ex(float(instant), result[1] & _model_mask(native))
                != epoch
            ):
                raise EphemerisSourceError("compressed_endpoint_unresolved")
            audit = _AUDIT.get()
            if audit is not None:
                changed = result[0] != original[0]
                audit["calls"] += 1
                audit["changed"] += int(changed)
                record = {
                    "operation": operation,
                    "input_julian_day": float(instant),
                    "physical_jd_tt": epoch,
                    "body_id": int(body),
                    "returned_flags": int(result[1]),
                    "original_native_state": list(original[0]),
                    "selected_native_state": list(result[0]),
                    "native_state_changed": changed,
                    "initial_windows": _public_windows(initial),
                    "selected_windows": _public_windows(selected),
                    "selection_anchor_jd_tt": anchors,
                    "physical_instant_shifted": False,
                }
                key = repr(record)
                if key in audit["records"] or len(audit["records"]) < 64:
                    audit["records"][key] = record
                else:
                    audit["omitted"] += 1
            return result
        ends = [w[2] for w in selected if abs(epoch - w[2]) <= pad]
        if not ends:
            break
    raise EphemerisSourceError("compressed_endpoint_unresolved")


def coordinate_context_evidence() -> dict[str, Any] | None:
    """Receipt for the immediately preceding requested physical coordinate."""
    return _LAST_COORDINATE.get()


def _lunar_light_path(
    native: Any,
    epoch: float,
    flags: int,
    invoke: Callable[[Any, str, tuple[Any, ...], dict[str, Any]], Any],
) -> dict[str, Any]:
    """Select by the physical reception path before the requested Moon state.

    Only called in the owned, identity-checked context. A same-epoch Sun
    preflight alone can select a file starting AFTER the lunar retarded epoch.
    No reference residual or neighbouring output chooses the source.
    """
    policy: dict[str, Any] = {
        "method_id": "owned_geocentric_lunar_light_path_v1",
        "reception_jd_tt": epoch,
        "requested_coordinate_flags": flags,
        "scope": "Geocentric apparent Moon source intervals; not a complete native read-set or accuracy certificate.",
    }
    if flags & (
        native.FLG_TRUEPOS | native.FLG_BARYCTR | native.FLG_HELCTR | native.FLG_TOPOCTR
    ):
        return {**policy, "status": "not_applied", "reason": "not_geocentric_apparent"}
    geometric_flags = (
        native.FLG_SWIEPH
        | native.FLG_SPEED
        | native.FLG_TRUEPOS
        | native.FLG_XYZ
        | native.FLG_EQUATORIAL
        | native.FLG_J2000
        | native.FLG_ICRS
    )
    geometric = _post_call_endpoint_guard(
        native, "calc", (epoch, native.MOON, geometric_flags), {}, invoke
    )
    if not _is_swiss(native, geometric):
        return {
            **policy,
            "status": "not_applied",
            "reason": "geometric_backend_not_swiss",
        }
    values = geometric[0]
    if len(values) != 6 or not all(math.isfinite(v) for v in values):
        raise EphemerisSourceError("coordinate_values_unavailable")
    radius = math.hypot(*values[:3])
    if radius <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    # Same constants as the inspected app_pos_etc_moon: AU metres, c m/s,
    # and seconds/day. This is a physical epoch, never a residual-based anchor.
    delay = radius * 149597870700.0 / 299792458.0 / 86400.0
    retarded = epoch - delay
    initial = _windows(native)
    if initial is None or not _valid(initial):
        raise EphemerisSourceError("lunar_source_window_incoherent")
    policy.update(
        geometric_native_state=list(values),
        geometric_returned_flags=int(geometric[1]),
        light_time_days=delay,
        retarded_jd_tt=retarded,
        initial_windows=_public_windows(initial),
    )
    if all(w[1] <= retarded <= epoch <= w[2] for w in initial):
        return {
            **policy,
            "status": "already_covered",
            "selected_windows": _public_windows(initial),
        }
    primed = _post_call_endpoint_guard(
        native,
        "calc",
        (retarded, native.MOON, geometric_flags | native.FLG_BARYCTR),
        {},
        invoke,
    )
    if not _is_swiss(native, primed):
        raise EphemerisSourceError("model_changed")
    selected = _windows(native)
    if (
        selected is None
        or not _valid(selected)
        or not all(w[1] <= retarded <= epoch <= w[2] for w in selected)
    ):
        raise EphemerisSourceError("lunar_source_window_incoherent")
    if [w[3] for w in selected] != [w[3] for w in initial]:
        raise EphemerisSourceError("edition_changed")
    if len(primed[0]) != 6 or not all(math.isfinite(v) for v in primed[0]):
        raise EphemerisSourceError("coordinate_values_unavailable")
    reception = _post_call_endpoint_guard(
        native, "calc", (epoch, native.MOON, geometric_flags), {}, invoke
    )
    if not _is_swiss(native, reception):
        raise EphemerisSourceError("model_changed")
    if len(reception[0]) != 6 or not all(math.isfinite(v) for v in reception[0]):
        raise EphemerisSourceError("coordinate_values_unavailable")
    selected_radius = math.hypot(*reception[0][:3])
    selected_delay = selected_radius * 149597870700.0 / 299792458.0 / 86400.0
    selected_retarded = epoch - selected_delay
    if (
        selected_radius <= 0
        or _windows(native) != selected
        or not all(w[1] <= selected_retarded <= epoch <= w[2] for w in selected)
    ):
        raise EphemerisSourceError("lunar_source_window_incoherent")
    return {
        **policy,
        "status": "reselected_common_window",
        "initial_light_time_days": delay,
        "selection_probe_jd_tt": retarded,
        "initial_geometric_native_state": list(values),
        "geometric_native_state": list(reception[0]),
        "light_time_days": selected_delay,
        "retarded_jd_tt": selected_retarded,
        "retarded_barycentric_native_state": list(primed[0]),
        "selected_windows": _public_windows(selected),
    }


def _solar_light_path(
    native: Any,
    epoch: float,
    flags: int,
    invoke: Callable[[Any, str, tuple[Any, ...], dict[str, Any]], Any],
) -> dict[str, Any]:
    """Retain app_pos_etc_sun's fixed observer and two exact Sun epochs.

    Public barycentric Sun calls also rebuild Earth as a native side effect.
    Rebuild both reception states before the original apparent request; never
    retain an Earth(t) from the file selected before the retarded Sun read.
    """
    policy: dict[str, Any] = {
        "method_id": "owned_geocentric_solar_light_path_v1",
        "source_function": "sweph.c:app_pos_etc_sun",
        "source_url": "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c#L3901",
        "reception_jd_tt": epoch,
        "requested_coordinate_flags": flags,
        "states": {},
        "scope": "Two exact retarded Sun evaluations and rebuilt reception observer in checked native source intervals; not an atomic read-set, derivative convergence or accuracy certificate.",
    }
    unsupported = (
        native.FLG_TRUEPOS
        | native.FLG_BARYCTR
        | native.FLG_HELCTR
        | native.FLG_TOPOCTR
        | native.FLG_SPEED3
        | getattr(native, "FLG_CENTER_BODY", 1048576)
    )
    if flags & unsupported:
        return {
            **policy,
            "status": "not_applied",
            "reason": "unsupported_observer_position_or_three_epoch_speed",
        }
    base = (
        native.FLG_SWIEPH
        | native.FLG_SPEED
        | native.FLG_TRUEPOS
        | native.FLG_XYZ
        | native.FLG_EQUATORIAL
        | native.FLG_J2000
        | native.FLG_ICRS
    )

    def state(at: float, body: int, barycentric: bool, label: str) -> tuple:
        requested = base | (native.FLG_BARYCTR if barycentric else 0)
        values, returned = _post_call_endpoint_guard(
            native, "calc", (at, body, requested), {}, invoke
        )
        required = (
            (requested & ~native.FLG_SWIEPH)
            | native.FLG_NONUT
            | native.FLG_NOABERR
            | native.FLG_NOGDEFL
        )
        forbidden = (
            native.FLG_SIDEREAL
            | native.FLG_RADIANS
            | native.FLG_HELCTR
            | native.FLG_TOPOCTR
        )
        if (
            returned < 0
            or returned & required != required
            or returned & forbidden
            or bool(returned & native.FLG_BARYCTR) != barycentric
        ):
            raise EphemerisSourceError("coordinate_contract_changed")
        if len(values) != 6 or not all(math.isfinite(v) for v in values):
            raise EphemerisSourceError("coordinate_values_unavailable")
        observed = _windows(native) if _is_swiss(native, (values, returned)) else None
        policy["states"][label] = {
            "epoch_jd_tt": at,
            "body_id": body,
            "requested_flags": requested,
            "returned_flags": returned,
            "native_state": list(values),
            "observed_file_windows": (
                _public_windows(observed)
                if observed is not None and _valid(observed)
                else []
            ),
        }
        return values, returned

    def selected() -> tuple:
        observed = _windows(native)
        if observed is None or not _valid(observed):
            raise EphemerisSourceError("dependency_source_window_incoherent")
        if len({w[3] for w in observed}) != 1:
            raise EphemerisSourceError("edition_changed")
        return observed

    probe = state(epoch, native.SUN, False, "initial_backend_probe")
    if not _is_swiss(native, probe):
        return {
            **policy,
            "status": "not_applied",
            "reason": "geometric_backend_not_swiss",
        }
    earth, earth_flags = state(epoch, native.EARTH, True, "initial_observer")
    sun, sun_flags = state(epoch, native.SUN, True, "initial_sun")
    if not _is_swiss(native, (earth, earth_flags)) or not _is_swiss(
        native, (sun, sun_flags)
    ):
        raise EphemerisSourceError("model_changed")
    initial = selected()
    policy["initial_windows"] = _public_windows(initial)

    def iterations(observer: Any, solar: Any, prefix: str) -> list[float] | None:
        epochs = []
        for index in range(2):
            displacement = [a - b for a, b in zip(observer[:3], solar[:3])]
            delay = (
                math.sqrt(sum(x * x for x in displacement))
                * 149597870700.0
                / 299792458.0
                / 86400.0
            )
            at = epoch - delay
            if not math.isfinite(delay) or delay <= 0 or not math.isfinite(at):
                raise EphemerisSourceError("coordinate_values_unavailable")
            windows = selected()
            if not all(w[1] <= at <= epoch <= w[2] for w in windows):
                backend = state(at, native.SUN, False, prefix + f"_backend_{index}")
                if not _is_swiss(native, backend):
                    return None
            solar, returned = state(at, native.SUN, True, prefix + f"_sun_{index}")
            if not _is_swiss(native, (solar, returned)):
                raise EphemerisSourceError("model_changed")
            epochs.append(at)
        return epochs

    epochs = iterations(earth, sun, "selection")
    if epochs is None:
        return {
            **policy,
            "status": "restore_before_auxiliary_fallback",
            "reason": "retarded_auxiliary_backend_not_swiss",
        }
    common = selected()
    if [w[3] for w in initial] != [w[3] for w in common] or not all(
        w[1] <= min(epochs) <= epoch <= w[2] for w in common
    ):
        raise EphemerisSourceError("dependency_source_window_incoherent")

    def reception(prefix: str) -> tuple:
        earth, returned_earth = state(epoch, native.EARTH, True, prefix + "_observer")
        sun, returned_sun = state(epoch, native.SUN, True, prefix + "_sun")
        if not _is_swiss(native, (earth, returned_earth)) or not _is_swiss(
            native, (sun, returned_sun)
        ):
            raise EphemerisSourceError("model_changed")
        if selected() != common:
            raise EphemerisSourceError("dependency_source_window_incoherent")
        return earth, sun

    earth, sun = reception("coherent")
    changed = initial != common
    if changed:
        refined = iterations(earth, sun, "refined")
        if (
            refined is None
            or selected() != common
            or not all(w[1] <= min(refined) <= epoch <= w[2] for w in common)
        ):
            raise EphemerisSourceError("dependency_source_window_incoherent")
        reception("final")
    else:
        refined = epochs
    return {
        **policy,
        "status": "reselected_common_window" if changed else "already_covered",
        "selection_retarded_epochs_jd_tt": epochs,
        "retarded_epochs_jd_tt": refined,
        "selected_windows": _public_windows(common),
    }


def _planet_light_path(
    native: Any,
    epoch: float,
    body: int,
    flags: int,
    invoke: Callable[[Any, str, tuple[Any, ...], dict[str, Any]], Any],
) -> dict[str, Any]:
    """Prepare the app_pos_etc_plan reception/retarded composite together.

    Called only after a fresh owned-context Sun preflight. The native two
    rough light-time iterations determine the dependency epoch; neither a
    residual nor a finite-difference estimate selects the source.
    """
    policy: dict[str, Any] = {
        "method_id": "owned_geocentric_planet_light_path_v1",
        "source_function": "sweph.c:app_pos_etc_plan",
        "source_url": "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c",
        "body_id": body,
        "reception_jd_tt": epoch,
        "requested_coordinate_flags": flags,
        "auxiliary_coordinate_kind": "ICRF_cartesian_AU_and_AU_per_day",
        "scope": "Checked observed source intervals for a geocentric apparent planet light path; not an atomic native read-set, derivative convergence or accuracy certificate.",
        "states": {},
    }
    unsupported = (
        native.FLG_TRUEPOS
        | native.FLG_BARYCTR
        | native.FLG_HELCTR
        | native.FLG_TOPOCTR
        | getattr(native, "FLG_CENTER_BODY", 1048576)
    )
    if flags & unsupported:
        return {
            **policy,
            "status": "not_applied",
            "reason": "not_supported_geocentric_apparent",
        }
    base = (
        native.FLG_SWIEPH
        | native.FLG_SPEED
        | native.FLG_TRUEPOS
        | native.FLG_XYZ
        | native.FLG_EQUATORIAL
        | native.FLG_J2000
        | native.FLG_ICRS
    )

    def state(
        at: float, target: int, barycentric: bool, label: str, *, probe: bool = False
    ) -> tuple[Any, int]:
        required_flags = base | (native.FLG_BARYCTR if barycentric else 0)
        values, returned = _post_call_endpoint_guard(
            native, "calc", (at, target, required_flags), {}, invoke
        )
        required = (
            (required_flags & ~native.FLG_SWIEPH)
            | native.FLG_NONUT
            | native.FLG_NOABERR
            | native.FLG_NOGDEFL
        )
        forbidden = (
            native.FLG_SIDEREAL
            | native.FLG_RADIANS
            | native.FLG_HELCTR
            | native.FLG_TOPOCTR
        )
        if (
            returned < 0
            or returned & required != required
            or returned & forbidden
            or bool(returned & native.FLG_BARYCTR) != barycentric
        ):
            raise EphemerisSourceError("coordinate_contract_changed")
        if len(values) != 6 or not all(math.isfinite(v) for v in values):
            raise EphemerisSourceError("coordinate_values_unavailable")
        swiss = _is_swiss(native, (values, returned))
        observed = _windows(native) if swiss else None
        policy["states"][label] = {
            "epoch_jd_tt": at,
            "body_id": target,
            "requested_flags": required_flags,
            "returned_flags": returned,
            "native_state": list(values),
            "observed_file_windows": (
                _public_windows(observed)
                if observed is not None and _valid(observed)
                else []
            ),
        }
        if not swiss and not probe:
            raise EphemerisSourceError("model_changed")
        return values, returned

    def selected() -> tuple[tuple[Any, ...], ...]:
        observed = _windows(native)
        if observed is None or not _valid(observed):
            raise EphemerisSourceError("dependency_source_window_incoherent")
        if len({w[3] for w in observed}) != 1:
            raise EphemerisSourceError("edition_changed")
        return observed

    def delay(target: Any, earth: Any) -> float:
        rough = target[:3]
        value = 0.0
        for _ in range(2):
            displacement = [a - b for a, b in zip(rough, earth[:3])]
            value = (
                math.sqrt(sum(x * x for x in displacement))
                * 149597870700.0
                / 299792458.0
                / 86400.0
            )
            rough = tuple(x - value * v for x, v in zip(target[:3], target[3:]))
        if not math.isfinite(value) or value <= 0:
            raise EphemerisSourceError("coordinate_values_unavailable")
        return value

    # Probe geometrically first: Moshier has no barycentric-state API, and
    # an automatic analytical fallback must not become a new native error.
    geometric = state(epoch, body, False, "initial_backend_probe", probe=True)
    if not _is_swiss(native, geometric):
        return {
            **policy,
            "status": "not_applied",
            "reason": "geometric_backend_not_swiss",
        }
    target, _ = state(epoch, body, True, "initial_body")
    earth, _ = state(epoch, native.EARTH, True, "initial_observer")
    initial = selected()
    light_time = delay(target, earth)
    retarded = epoch - light_time
    policy.update(
        light_time_days=light_time,
        retarded_jd_tt=retarded,
        initial_windows=_public_windows(initial),
    )
    if all(w[1] <= retarded <= epoch <= w[2] for w in initial):
        return {
            **policy,
            "status": "already_covered",
            "selected_windows": _public_windows(initial),
        }
    retarded_probe = state(retarded, body, False, "retarded_backend_probe", probe=True)
    if not _is_swiss(native, retarded_probe):
        return {
            **policy,
            "status": "restore_before_native_fallback",
            "reason": "retarded_geometric_backend_not_swiss",
        }
    state(retarded, native.EARTH, True, "retarded_observer")
    state(retarded, body, True, "retarded_body")
    common = selected()
    if not all(w[1] <= retarded <= epoch <= w[2] for w in common) or [
        w[3] for w in initial
    ] != [w[3] for w in common]:
        raise EphemerisSourceError("dependency_source_window_incoherent")
    # Explicitly rebuild BOTH reception states after the retarded evaluation.
    # Replaying only the target can retain an Earth(t) from the newer fit.
    earth, _ = state(epoch, native.EARTH, True, "coherent_observer")
    target, _ = state(epoch, body, True, "coherent_body")
    refined = delay(target, earth)
    if selected() != common or not all(
        w[1] <= epoch - refined <= epoch <= w[2] for w in common
    ):
        raise EphemerisSourceError("dependency_source_window_incoherent")
    return {
        **policy,
        "status": "reselected_common_window",
        "initial_light_time_days": light_time,
        "selection_probe_jd_tt": retarded,
        "light_time_days": refined,
        "retarded_jd_tt": epoch - refined,
        "selected_windows": _public_windows(common),
    }


def _external_solar_rebuild(
    native: Any,
    operation: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    instant: Any,
    flags: int,
    initial: Any,
    invoke: Callable[[Any, str, tuple[Any, ...], dict[str, Any]], Any],
) -> Any:
    """Rebuild a witnessed Swiss Sun's dependencies without owning its cache.

    app_pos_etc_sun can retain Earth(t) from a different compressed fit than
    Sun(t-tau). File metadata alone cannot reveal that mixed state. Reuse the
    two-node source recipe, then repeat the exact original request. No reset,
    nearby replacement epoch, residual-based source choice or rate exemption.
    """
    if not _is_swiss(native, initial):
        return initial
    epoch = float(instant)
    if operation == "calc_ut":
        epoch += native.deltat_ex(epoch, native.FLG_SWIEPH)
    solar = _solar_light_path(native, epoch, flags, invoke)
    if solar["status"] == "not_applied":
        return initial
    if solar["status"] not in {"already_covered", "reselected_common_window"}:
        raise EphemerisSourceError("dependency_source_window_incoherent")
    result = _post_call_endpoint_guard(native, operation, args, kwargs, invoke)
    windows = _windows(native)
    if (
        not _is_swiss(native, result)
        or result[1] != initial[1]
        or windows is None
        or not _valid(windows)
        or _public_windows(windows) != solar["selected_windows"]
        or len(result[0]) != 6
        or not all(math.isfinite(value) for value in result[0])
    ):
        raise EphemerisSourceError("dependency_source_window_incoherent")
    _LAST_COORDINATE.set(
        {
            "policy_id": POLICY_ID,
            "dependency_rebuild_method_id": "external_geocentric_solar_dependency_rebuild_v1",
            "operation": operation,
            "input_julian_day": float(instant),
            "physical_jd_tt": epoch,
            "body_id": native.SUN,
            "returned_flags": int(result[1]),
            "selected_native_state": list(result[0]),
            "original_native_state": list(initial[0]),
            "native_state_changed": result != initial,
            "original_target_state_status": "observed_before_dependency_rebuild",
            "private_native_cache_reset": False,
            "selected_windows": _public_windows(windows),
            "physical_instant_shifted": False,
            "solar_light_path": solar,
            "scope": "Exact original Sun request after checked reception/retarded dependency reconstruction. External cache/configuration is not reset or owned; observed file contexts are not an atomic read-set or physical accuracy certificate.",
        }
    )
    return result


def compressed_endpoint_call(
    native: Any,
    operation: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    invoke: Callable[[Any, str, tuple[Any, ...], dict[str, Any]], Any],
    *,
    configured_path: Callable[[], str | None] = lambda: None,
) -> Any:
    """Own caches only inside the explicit private-operation audit context.

    An earlier unwrapped call can leave target coefficients cached even after
    a Sun preflight or a nearby target replay. Clearing that state is necessary
    before source selection; a target's untrusted old result is not evaluated
    or invented for the receipt. No reset of an external caller's configuration.
    """
    audit = _AUDIT.get()
    if operation in {"calc", "calc_ut"}:
        _LAST_COORDINATE.set(None)
    body = args[1] if len(args) > 1 else kwargs.get("planet")
    instant = (
        args[0] if args else kwargs.get("tjdet" if operation == "calc" else "tjdut")
    )
    flags = (
        args[2]
        if len(args) > 2
        else kwargs.get(
            "flags",
            getattr(native, "FLG_SWIEPH", 2) | getattr(native, "FLG_SPEED", 256),
        )
    )
    observer_sample = _OBSERVER_SAMPLE.get()
    if observer_sample is not None:
        required = (
            native.FLG_SPEED
            | native.FLG_XYZ
            | native.FLG_TRUEPOS
            | native.FLG_SIDEREAL
            | native.FLG_BARYCTR
        )
        forbidden = (
            native.FLG_EQUATORIAL
            | native.FLG_J2000
            | native.FLG_ICRS
            | native.FLG_RADIANS
            | native.FLG_HELCTR
            | native.FLG_TOPOCTR
        )
        if (
            operation != "calc"
            or instant != observer_sample
            or body != native.EARTH
            or not isinstance(flags, int)
            or flags & required != required
            or flags & forbidden
        ):
            raise EphemerisSourceError("observer_source_window_incoherent")
    eligible = (
        operation in {"calc", "calc_ut"}
        and isinstance(body, int)
        and body in {*range(10), 14}
        and isinstance(instant, (int, float))
        and math.isfinite(instant)
        and isinstance(flags, int)
        and flags & _model_mask(native) in {0, native.FLG_SWIEPH}
        and str(getattr(native, "version", "unavailable")) == "2.10.03"
        and binding_distribution_version(native, version) == "2.10.3.2"
    )
    managed = audit is not None and _DEPENDENCY_CONTEXT.get() is None and eligible
    if not managed:
        dependent = _DEPENDENCY_CONTEXT.get()
        if dependent is not None and operation in {"calc", "calc_ut"}:
            if operation != "calc" or instant != dependent:
                raise EphemerisSourceError("dependency_source_window_incoherent")
        result = _post_call_endpoint_guard(native, operation, args, kwargs, invoke)
        if audit is None and dependent is None and eligible and body == native.SUN:
            return _external_solar_rebuild(
                native, operation, args, kwargs, instant, flags, result, invoke
            )
        if (
            dependent is not None
            and operation == "calc"
            and not _is_swiss(native, result)
        ):
            raise EphemerisSourceError("model_changed")
        return result
    assert audit is not None and isinstance(body, int) and instant is not None
    # The process owns these settings; set_ephe_path's cache/model reset must
    # never be applied to an arbitrary parent's configured native library.
    native.set_ephe_path(configured_path() or "")
    audit["resets"] += 1
    origin_mask = native.FLG_HELCTR | native.FLG_BARYCTR
    # Native plaus_iflag() makes topocentric override helio/barycentric.
    preflight_origin = 0 if flags & native.FLG_TOPOCTR else flags & origin_mask
    identity_reference = (
        body == native.EARTH
        and not preflight_origin
        or body == native.SUN
        and preflight_origin == native.FLG_HELCTR
    )
    if body == native.EARTH and not preflight_origin:
        preflight_origin = native.FLG_HELCTR
    model_probe_flags = None
    if preflight_origin == native.FLG_HELCTR and not identity_reference:
        # A heliocentric Sun is zero and primes no coefficients. Inspect only
        # this probe's model, discard its coordinates and clear its possibly
        # mixed observer state before choosing a Sun-vector preflight.
        probe = invoke(
            native,
            operation,
            (instant, native.SUN, native.FLG_SWIEPH | native.FLG_TRUEPOS),
            {},
        )
        model_probe_flags = int(probe[1])
        if _is_swiss(native, probe):
            preflight_origin = native.FLG_BARYCTR
        elif model_probe_flags & _model_mask(native) != native.FLG_MOSEPH:
            raise EphemerisSourceError("coordinate_model_changed")
        native.set_ephe_path(configured_path() or "")
        audit["resets"] += 1
    preflight_flags = native.FLG_SWIEPH | native.FLG_TRUEPOS | preflight_origin
    _post_call_endpoint_guard(
        native,
        operation,
        (instant, native.SUN, preflight_flags),
        {},
        invoke,
    )
    solar = None
    lunar = None
    planet = None
    if body == native.SUN:
        reception_tt = float(instant)
        if operation == "calc_ut":
            reception_tt += native.deltat_ex(reception_tt, native.FLG_SWIEPH)
        solar = _solar_light_path(native, reception_tt, flags, invoke)
        if solar["status"] == "restore_before_auxiliary_fallback":
            native.set_ephe_path(configured_path() or "")
            audit["resets"] += 1
            _post_call_endpoint_guard(
                native,
                operation,
                (instant, native.SUN, preflight_flags),
                {},
                invoke,
            )
            solar.update(status="not_applied", native_context_restarted=True)
    elif body == native.MOON:
        reception_tt = float(instant)
        if operation == "calc_ut":
            reception_tt += native.deltat_ex(reception_tt, native.FLG_SWIEPH)
        lunar = _lunar_light_path(native, reception_tt, flags, invoke)
    elif body in range(2, 10):
        reception_tt = float(instant)
        if operation == "calc_ut":
            reception_tt += native.deltat_ex(reception_tt, native.FLG_SWIEPH)
        planet = _planet_light_path(native, reception_tt, body, flags, invoke)
        if planet["status"] == "restore_before_native_fallback":
            # Return backend choice to the original request from a fresh
            # context. Never run an unsupported barycentric Moshier call.
            native.set_ephe_path(configured_path() or "")
            audit["resets"] += 1
            _post_call_endpoint_guard(
                native,
                operation,
                (instant, native.SUN, preflight_flags),
                {},
                invoke,
            )
    result = _post_call_endpoint_guard(native, operation, args, kwargs, invoke)
    if len(result[0]) != 6 or not all(math.isfinite(x) for x in result[0]):
        raise EphemerisSourceError("coordinate_values_unavailable")
    epoch = float(instant)
    if operation == "calc_ut":
        epoch += native.deltat_ex(epoch, result[1] & _model_mask(native))
    windows = (
        _physical_windows(native, body, result[1])
        if _is_swiss(native, result)
        else None
    )
    if solar is not None and solar["status"] in {
        "already_covered",
        "reselected_common_window",
    }:
        if not _is_swiss(native, result):
            raise EphemerisSourceError("model_changed")
        if (
            windows is None
            or not _valid(windows)
            or _public_windows(windows) != solar["selected_windows"]
            or epoch != solar["reception_jd_tt"]
        ):
            raise EphemerisSourceError("dependency_source_window_incoherent")
    if planet is not None:
        if planet["status"] == "restore_before_native_fallback":
            if _is_swiss(native, result):
                raise EphemerisSourceError("dependency_source_window_incoherent")
            planet.update(status="not_applied", native_fallback_restarted=True)
        elif planet["status"] in {"already_covered", "reselected_common_window"}:
            if not _is_swiss(native, result):
                raise EphemerisSourceError("model_changed")
            if (
                windows is None
                or not _valid(windows)
                or _public_windows(windows) != planet["selected_windows"]
                or epoch != planet["reception_jd_tt"]
            ):
                raise EphemerisSourceError("dependency_source_window_incoherent")
    if lunar is not None and lunar["status"] in {
        "already_covered",
        "reselected_common_window",
    }:
        if (
            windows is None
            or not _valid(windows)
            or _public_windows(windows) != lunar["selected_windows"]
            or epoch != lunar["reception_jd_tt"]
        ):
            raise EphemerisSourceError("lunar_source_window_incoherent")
    _LAST_COORDINATE.set(
        {
            "policy_id": POLICY_ID,
            "operation": operation,
            "input_julian_day": float(instant),
            "physical_jd_tt": epoch,
            "body_id": body,
            "returned_flags": int(result[1]),
            "selected_native_state": list(result[0]),
            "original_native_state": None,
            "native_state_changed": None,
            "original_target_state_status": "not_evaluated_before_context_reset",
            "private_native_cache_reset": True,
            "preflight_reference": "same_reception_epoch_geometric_Sun",
            **(
                {
                    "preflight_requested_flags": preflight_flags,
                    "preflight_reference_origin": (
                        "barycentric"
                        if preflight_origin & native.FLG_BARYCTR
                        else "heliocentric"
                    ),
                    "preflight_establishes_geocentric_observer": False,
                    "preflight_solar_vector_is_defined_zero": preflight_origin
                    == native.FLG_HELCTR,
                    "coordinate_reference_origin": (
                        "barycentric"
                        if result[1] & native.FLG_BARYCTR
                        else (
                            "heliocentric"
                            if result[1] & native.FLG_HELCTR
                            else (
                                "topocentric"
                                if result[1] & native.FLG_TOPOCTR
                                else "geocentric"
                            )
                        )
                    ),
                    "coordinate_is_defined_zero": not _physical_slots(
                        native, body, result[1]
                    ),
                    "coordinate_represents_physical_body_vector": bool(
                        _physical_slots(native, body, result[1])
                    ),
                    **(
                        {
                            "preflight_model_probe": {
                                "returned_flags": model_probe_flags,
                                "coordinates_discarded": True,
                                "native_context_reset_after_probe": True,
                                "physical_source_certified": False,
                            }
                        }
                        if model_probe_flags is not None
                        else {}
                    ),
                }
                if preflight_origin
                else {}
            ),
            "selected_windows": (
                _public_windows(windows)
                if windows is not None and _valid(windows)
                else []
            ),
            "physical_instant_shifted": False,
            **({"solar_light_path": solar} if solar is not None else {}),
            **({"lunar_light_path": lunar} if lunar is not None else {}),
            **({"planet_light_path": planet} if planet is not None else {}),
            "scope": "Requested target and frame after fresh private source preselection. The untrusted target state was not computed before resetting caches; no exact-preservation claim against that unknown state. Physical backend remains the returned model, including any declared fallback.",
        }
    )
    return result
