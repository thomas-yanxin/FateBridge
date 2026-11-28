"""Repair witnessed Swiss compressed-file endpoints before returning a state.

Swiss 2.10.03 retains a file at its inclusive final epoch. That context can
return an erroneous state. Select the adjacent context from its header alone,
then recalculate the *original* operation and arguments. This is not an epoch
shift, a new ephemeris, a universal cache normalization or an accuracy proof.
The caller must hold the shared native-runtime lock throughout.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import Protocol, TypedDict, TypeGuard

from typing_extensions import NotRequired

from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.utils.errors import EphemerisSourceError

_BINDING_VERSIONS: dict[tuple[int, str, str], str] = {}


class _NativeEphemeris(Protocol):
    FLG_SWIEPH: int
    FLG_MOSEPH: int
    FLG_JPLEPH: int
    FLG_SPEED: int
    FLG_SPEED3: int
    FLG_TRUEPOS: int
    FLG_BARYCTR: int
    FLG_HELCTR: int
    FLG_TOPOCTR: int
    FLG_XYZ: int
    FLG_EQUATORIAL: int
    FLG_J2000: int
    FLG_ICRS: int
    FLG_SIDEREAL: int
    FLG_RADIANS: int
    FLG_NONUT: int
    FLG_NOABERR: int
    FLG_NOGDEFL: int
    SUN: int
    MOON: int
    EARTH: int
    version: object

    def set_ephe_path(self, path: str) -> object: ...

    def deltat_ex(self, jd: float, flags: int) -> float: ...


NativeInvoker = Callable[
    [_NativeEphemeris, str, tuple[object, ...], dict[str, object]], object
]
_FileWindow = tuple[str, float, float, int]
_FileWindows = tuple[_FileWindow, ...]


class PublicWindow(TypedDict):
    slot: int
    filename: str
    start_jd_tt: float
    end_jd_tt: float
    de_number: int


class EndpointRecord(TypedDict):
    operation: str
    input_julian_day: float
    physical_jd_tt: float
    body_id: int
    returned_flags: int
    original_native_state: list[float]
    selected_native_state: list[float]
    native_state_changed: bool
    initial_windows: list[PublicWindow]
    selected_windows: list[PublicWindow]
    selection_anchor_jd_tt: list[float]
    physical_instant_shifted: bool


class EndpointContextEvidence(TypedDict):
    policy_id: str
    trigger: str
    endpoint_guard_trigger: str
    input_instant_shifted: bool
    native_coordinates_may_be_corrected: bool
    context_strategy: str
    native_cache_resets_so_far: int | None
    reference_preflight: str
    calls_corrected_so_far: int | None
    native_states_changed_so_far: int | None
    records: list[EndpointRecord]
    unrecorded_calls_at_record_limit: int
    scope: str


class LightPathState(TypedDict):
    epoch_jd_tt: float
    body_id: int
    requested_flags: int
    returned_flags: int
    native_state: list[float]
    observed_file_windows: list[PublicWindow]


class LunarLightPathPolicy(TypedDict):
    method_id: str
    reception_jd_tt: float
    requested_coordinate_flags: int
    scope: str
    status: str
    reason: NotRequired[str]
    geometric_native_state: NotRequired[list[float]]
    geometric_returned_flags: NotRequired[int]
    light_time_days: NotRequired[float]
    retarded_jd_tt: NotRequired[float]
    initial_windows: NotRequired[list[PublicWindow]]
    selected_windows: NotRequired[list[PublicWindow]]
    initial_light_time_days: NotRequired[float]
    selection_probe_jd_tt: NotRequired[float]
    initial_geometric_native_state: NotRequired[list[float]]
    retarded_barycentric_native_state: NotRequired[list[float]]


class SolarLightPathPolicy(TypedDict):
    method_id: str
    source_function: str
    reception_jd_tt: float
    requested_coordinate_flags: int
    states: dict[str, LightPathState]
    scope: str
    status: str
    reason: NotRequired[str]
    initial_windows: NotRequired[list[PublicWindow]]
    selection_retarded_epochs_jd_tt: NotRequired[list[float]]
    retarded_epochs_jd_tt: NotRequired[list[float]]
    selected_windows: NotRequired[list[PublicWindow]]
    native_context_restarted: NotRequired[bool]


class PlanetLightPathPolicy(TypedDict):
    method_id: str
    source_function: str
    body_id: int
    reception_jd_tt: float
    requested_coordinate_flags: int
    auxiliary_coordinate_kind: str
    scope: str
    states: dict[str, LightPathState]
    status: str
    reason: NotRequired[str]
    light_time_days: NotRequired[float]
    retarded_jd_tt: NotRequired[float]
    initial_windows: NotRequired[list[PublicWindow]]
    selected_windows: NotRequired[list[PublicWindow]]
    initial_light_time_days: NotRequired[float]
    selection_probe_jd_tt: NotRequired[float]
    native_fallback_restarted: NotRequired[bool]


class PreflightModelProbe(TypedDict):
    returned_flags: int
    coordinates_discarded: bool
    native_context_reset_after_probe: bool
    physical_source_certified: bool


class CoordinateContextEvidence(TypedDict):
    policy_id: str
    operation: str
    input_julian_day: float
    physical_jd_tt: float
    body_id: int
    returned_flags: int
    selected_native_state: list[float]
    original_native_state: None
    native_state_changed: None
    original_target_state_status: str
    private_native_cache_reset: bool
    preflight_reference: str
    selected_windows: list[PublicWindow]
    physical_instant_shifted: bool
    scope: str
    preflight_requested_flags: NotRequired[int]
    preflight_reference_origin: NotRequired[str]
    preflight_establishes_geocentric_observer: NotRequired[bool]
    preflight_solar_vector_is_defined_zero: NotRequired[bool]
    coordinate_reference_origin: NotRequired[str]
    coordinate_is_defined_zero: NotRequired[bool]
    coordinate_represents_physical_body_vector: NotRequired[bool]
    preflight_model_probe: NotRequired[PreflightModelProbe]
    solar_light_path: NotRequired[SolarLightPathPolicy]
    lunar_light_path: NotRequired[LunarLightPathPolicy]
    planet_light_path: NotRequired[PlanetLightPathPolicy]


@dataclass
class _AuditState:
    calls: int = 0
    changed: int = 0
    records: dict[str, EndpointRecord] = field(default_factory=dict)
    omitted: int = 0
    resets: int = 0


@dataclass(frozen=True)
class _CompressedEndpointState:
    audit: _AuditState | None = None
    last_coordinate: CoordinateContextEvidence | None = None
    dependency_context: float | None = None
    dependency_reception: CoordinateContextEvidence | None = None
    observer_sample: float | None = None


def _cached_binding_version(native: object) -> str:
    """Resolve binding distribution version once per native module identity."""
    if binding_distribution_version is not _ORIG_BINDING_DIST_VERSION:
        return binding_distribution_version(native, version)
    native_ver = str(getattr(native, "version", "unavailable"))
    file_key = str(getattr(native, "__file__", ""))
    key = (id(native), file_key, native_ver)
    cached = _BINDING_VERSIONS.get(key)
    if cached is None:
        cached = binding_distribution_version(native, version)
        _BINDING_VERSIONS[key] = cached
    return cached


_ORIG_BINDING_DIST_VERSION = binding_distribution_version

POLICY_ID = "compressed_file_endpoint_context_v5"
_CONTEXT: ContextVar[_CompressedEndpointState] = ContextVar(
    "compressed_endpoint_context", default=_CompressedEndpointState()
)


@contextmanager
def preserve_native_observer_sample_context(
    reception_tt: float, sample_tt: float, model: str, *, native: _NativeEphemeris
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
    previous = _CONTEXT.get()
    reception = previous.last_coordinate or previous.dependency_reception
    if model == "swieph":
        pad = 64 * math.ulp(sample_tt)
        if (
            before is None
            or not _valid(before)
            or not all(
                w[1] <= reception_tt <= w[2] and w[1] + pad < sample_tt < w[2] - pad
                for w in before
            )
            or previous.audit is not None
            and (
                reception is None
                or not reception.get("private_native_cache_reset")
                or reception.get("physical_jd_tt") != reception_tt
                or reception.get("selected_windows") != _public_windows(before)
            )
        ):
            raise EphemerisSourceError("observer_source_window_incoherent")
    prev_sample = previous.observer_sample
    prev_dep = previous.dependency_context
    prev_rec = previous.dependency_reception
    _CONTEXT.set(
        replace(
            previous,
            observer_sample=sample_tt,
            dependency_context=(sample_tt if model == "swieph" else prev_dep),
            dependency_reception=reception,
        )
    )
    try:
        yield
        if model == "swieph" and _windows(native) != before:
            raise EphemerisSourceError("observer_source_window_incoherent")
    finally:
        _CONTEXT.set(
            replace(
                _CONTEXT.get(),
                dependency_reception=prev_rec,
                dependency_context=prev_dep,
                observer_sample=prev_sample,
            )
        )


@contextmanager
def preserve_native_dependency_context(
    reception_tt: float, sample_tt: float, model: str, *, native: _NativeEphemeris
) -> Iterator[None]:
    """Retain an already selected source for one checked retarded dependency.

    This does not bypass the source guard. Both epochs must fit the observed
    windows, which must stay identical through the dependent call. Use only
    under the native lock after the reception state was freshly established.
    """
    previous = _CONTEXT.get()
    if previous.audit is None or model != "swieph":
        yield
        return
    before = _windows(native)
    reception = previous.last_coordinate
    if reception is None and previous.dependency_context is not None:
        reception = previous.dependency_reception
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
    prev_dep = previous.dependency_context
    prev_rec = previous.dependency_reception
    _CONTEXT.set(
        replace(previous, dependency_context=sample_tt, dependency_reception=reception)
    )
    try:
        yield
        if _windows(native) != before:
            raise EphemerisSourceError("dependency_source_window_incoherent")
    finally:
        _CONTEXT.set(
            replace(
                _CONTEXT.get(),
                dependency_reception=prev_rec,
                dependency_context=prev_dep,
            )
        )


@contextmanager
def audit_compressed_endpoints() -> Iterator[None]:
    """Keep bounded diagnostics for one private calculation, including repeats."""
    previous = _CONTEXT.get()
    if previous.audit is not None:
        yield
        return
    _CONTEXT.set(replace(previous, audit=_AuditState(), last_coordinate=None))
    try:
        yield
    finally:
        # The private calls changed native caches. A receipt from before this
        # outer audit cannot describe their current state and must not leak.
        _CONTEXT.set(
            replace(_CONTEXT.get(), audit=previous.audit, last_coordinate=None)
        )


def endpoint_context_evidence() -> EndpointContextEvidence:
    audit = _CONTEXT.get().audit
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
        "native_cache_resets_so_far": audit.resets if audit else None,
        "reference_preflight": "same_reception_epoch_geometric_Sun",
        "calls_corrected_so_far": audit.calls if audit else None,
        "native_states_changed_so_far": audit.changed if audit else None,
        "records": list(audit.records.values()) if audit else [],
        "unrecorded_calls_at_record_limit": audit.omitted if audit else 0,
        "scope": "Within the owned private operation, reset computed native state using the same path and preselect with a same-reception-epoch geometric Sun. For supported geocentric apparent Sun/Moon/planet requests, establish the checked reception/retarded light-path context before the exact original coordinate call. Native owned default model/tidal settings are reapplied; sidereal/topocentric parameters and fixed Delta-T survive set_ephe_path. Outside that operation, supported Swiss geocentric apparent Sun calls rebuild reception dependencies in their checked common source windows without resetting caller configuration; other calls retain the post-call endpoint guard. Correction counts describe preflight or requested native subcalls, not independent samples or proof that an unevaluated original target changed. No atomic read-set or physical accuracy certificate.",
    }


def _windows(native: object) -> _FileWindows | None:
    getter = getattr(native, "get_current_file_data", None)
    if not callable(getter):
        return None
    slot0 = tuple(getter(0))
    slot1 = tuple(getter(1))
    if not _is_file_window(slot0) or not _is_file_window(slot1):
        return None
    return (slot0, slot1)


def _is_file_window(window: tuple[object, ...]) -> TypeGuard[_FileWindow]:
    return (
        len(window) == 4
        and isinstance(window[0], str)
        and isinstance(window[1], (int, float))
        and not isinstance(window[1], bool)
        and isinstance(window[2], (int, float))
        and not isinstance(window[2], bool)
        and isinstance(window[3], int)
        and not isinstance(window[3], bool)
    )


def _valid(windows: _FileWindows) -> bool:
    return all(
        len(w) == 4
        and bool(w[0])
        and math.isfinite(w[1])
        and math.isfinite(w[2])
        and w[1] < w[2]
        for w in windows
    )


def _public_windows(windows: _FileWindows) -> list[PublicWindow]:
    return [
        {
            "slot": slot,
            "filename": _path_name(w[0]),
            "start_jd_tt": float(w[1]),
            "end_jd_tt": float(w[2]),
            "de_number": int(w[3]),
        }
        for slot, w in enumerate(windows)
    ]


def _is_swiss_result(
    result: object, native: _NativeEphemeris
) -> TypeGuard[tuple[Sequence[float], int]]:
    return bool(
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[0], Sequence)
        and not isinstance(result[0], (str, bytes))
        and isinstance(result[1], int)
        and not isinstance(result[1], bool)
        and result[1] >= 0
        and result[1] & _model_mask(native) == native.FLG_SWIEPH
    )


def _is_swiss(native: _NativeEphemeris, result: object) -> bool:
    return _is_swiss_result(result, native)


def _model_mask(native: _NativeEphemeris) -> int:
    return int(native.FLG_SWIEPH | native.FLG_MOSEPH | native.FLG_JPLEPH)


def _physical_slots(native: _NativeEphemeris, body: int, flags: int) -> tuple[int, ...]:
    """Use the effective native origin, not a possibly overridden request."""
    helio = int(getattr(native, "FLG_HELCTR", 8))
    bary = int(getattr(native, "FLG_BARYCTR", 16384))
    origin = flags & (helio | bary)
    if body == 14 and not origin or body == 0 and origin == helio:
        return ()  # Native reference identities, not physical vectors.
    if body in {1, 14} or not origin:
        return (0, 1)
    return (0,)


def _physical_windows(
    native: _NativeEphemeris, body: int, flags: int, observed: _FileWindows | None
) -> _FileWindows | None:
    slots = _physical_slots(native, body, flags)
    if not slots:
        return ()
    return None if observed is None else tuple(observed[slot] for slot in slots)


def _require_observer_windows(
    native: _NativeEphemeris,
    body: int,
    flags: int,
    epoch: float,
    windows: _FileWindows,
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
        _cached_binding_version(native),
    ) != ("2.10.03", "2.10.3.2"):
        return
    if (
        len(windows) != len(slots)
        or not _valid(windows)
        or not all(w[1] <= epoch <= w[2] for w in windows)
    ):
        raise EphemerisSourceError("swiss_dependency_unavailable")


def _native_invoke_errors(native: object) -> tuple[type[BaseException], ...]:
    native_error = getattr(native, "Error", None)
    base: tuple[type[BaseException], ...] = (
        RuntimeError,
        OSError,
        ValueError,
        TypeError,
        ArithmeticError,
    )
    if isinstance(native_error, type) and issubclass(native_error, BaseException):
        return (native_error, *base)
    return base


def _post_call_endpoint_guard(
    native: _NativeEphemeris,
    operation: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    invoke: NativeInvoker,
) -> tuple[object, _FileWindows | None]:
    """Return the native value and its final same-call full-slot observation."""
    result = invoke(native, operation, args, kwargs)
    if operation not in {"calc", "calc_ut"}:
        return result, None
    body = args[1] if len(args) > 1 else kwargs.get("planet")
    # Physical Sun through Pluto and Earth. Analytical nodes/fictitious factors
    # can leave unrelated file slots populated and must not trigger this rule.
    if (
        not isinstance(body, int)
        or isinstance(body, bool)
        or body not in {*range(10), 14}
        or not _is_swiss_result(result, native)
    ):
        return result, None
    instant = (
        args[0] if args else kwargs.get("tjdet" if operation == "calc" else "tjdut")
    )
    if (
        instant is None
        or isinstance(instant, bool)
        or not isinstance(instant, (int, float))
        or not math.isfinite(instant)
    ):
        return result, None
    raw_flags = (
        args[2]
        if len(args) > 2
        else kwargs.get("flags", native.FLG_SWIEPH | native.FLG_SPEED)
    )
    flags = (
        raw_flags
        if isinstance(raw_flags, int) and not isinstance(raw_flags, bool)
        else (native.FLG_SWIEPH | native.FLG_SPEED)
    )
    epoch = float(instant)
    if operation == "calc_ut":
        epoch += native.deltat_ex(epoch, result[1] & _model_mask(native))
    observed = _windows(native) if _physical_slots(native, body, result[1]) else None
    initial = _physical_windows(native, body, result[1], observed)
    if initial is None:
        return result, None
    pad = 64 * math.ulp(epoch)
    ends = [w[2] for w in initial if len(w) == 4 and w[0] and abs(epoch - w[2]) <= pad]
    if not ends:
        _require_observer_windows(native, body, result[1], epoch, initial)
        return result, observed
    if not _valid(initial):
        raise EphemerisSourceError("compressed_endpoint_unresolved")
    if (
        str(getattr(native, "version", "unavailable")),
        _cached_binding_version(native),
    ) != ("2.10.03", "2.10.3.2"):
        raise EphemerisSourceError("compressed_endpoint_unverified")
    original = result
    anchors: list[float] = []
    invoke_errors = _native_invoke_errors(native)
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
        except invoke_errors as error:
            raise EphemerisSourceError("compressed_endpoint_unresolved") from error
        if not _is_swiss_result(result, native):
            raise EphemerisSourceError("model_changed")
        if result[1] != original[1]:
            raise EphemerisSourceError("coordinate_contract_changed")
        observed = _windows(native)
        selected = _physical_windows(native, body, result[1], observed)
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
            audit = _CONTEXT.get().audit
            if audit is not None:
                changed = result[0] != original[0]
                audit.calls += 1
                audit.changed += int(changed)
                record: EndpointRecord = {
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
                if key in audit.records or len(audit.records) < 64:
                    audit.records[key] = record
                else:
                    audit.omitted += 1
            if operation == "calc_ut":
                # Delta-T can update native tidal/source context. Do not carry
                # an observation across that native operation.
                observed = _windows(native)
            return result, observed
        ends = [w[2] for w in selected if abs(epoch - w[2]) <= pad]
        if not ends:
            break
    raise EphemerisSourceError("compressed_endpoint_unresolved")


def coordinate_context_evidence() -> CoordinateContextEvidence | None:
    """Receipt for the immediately preceding requested physical coordinate."""
    return _CONTEXT.get().last_coordinate


def _lunar_light_path(
    native: _NativeEphemeris,
    epoch: float,
    flags: int,
    invoke: NativeInvoker,
) -> LunarLightPathPolicy:
    """Select by the physical reception path before the requested Moon state.

    Only called in the owned, identity-checked context. A same-epoch Sun
    preflight alone can select a file starting AFTER the lunar retarded epoch.
    No reference residual or neighbouring output chooses the source.
    """
    base_method = "owned_geocentric_lunar_light_path_v1"
    base_scope = "Geocentric apparent Moon source intervals; not a complete native read-set or accuracy certificate."
    if flags & (
        native.FLG_TRUEPOS | native.FLG_BARYCTR | native.FLG_HELCTR | native.FLG_TOPOCTR
    ):
        return {
            "method_id": base_method,
            "reception_jd_tt": epoch,
            "requested_coordinate_flags": flags,
            "scope": base_scope,
            "status": "not_applied",
            "reason": "not_geocentric_apparent",
        }
    geometric_flags = (
        native.FLG_SWIEPH
        | native.FLG_SPEED
        | native.FLG_TRUEPOS
        | native.FLG_XYZ
        | native.FLG_EQUATORIAL
        | native.FLG_J2000
        | native.FLG_ICRS
    )
    geometric, _ = _post_call_endpoint_guard(
        native, "calc", (epoch, native.MOON, geometric_flags), {}, invoke
    )
    if not _is_swiss_result(geometric, native):
        return {
            "method_id": base_method,
            "reception_jd_tt": epoch,
            "requested_coordinate_flags": flags,
            "scope": base_scope,
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
    initial_public = _public_windows(initial)
    if all(w[1] <= retarded <= epoch <= w[2] for w in initial):
        return {
            "method_id": base_method,
            "reception_jd_tt": epoch,
            "requested_coordinate_flags": flags,
            "scope": base_scope,
            "geometric_native_state": list(values),
            "geometric_returned_flags": int(geometric[1]),
            "light_time_days": delay,
            "retarded_jd_tt": retarded,
            "initial_windows": initial_public,
            "status": "already_covered",
            "selected_windows": initial_public,
        }
    primed, _ = _post_call_endpoint_guard(
        native,
        "calc",
        (retarded, native.MOON, geometric_flags | native.FLG_BARYCTR),
        {},
        invoke,
    )
    if not _is_swiss_result(primed, native):
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
    reception, _ = _post_call_endpoint_guard(
        native, "calc", (epoch, native.MOON, geometric_flags), {}, invoke
    )
    if not _is_swiss_result(reception, native):
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
        "method_id": base_method,
        "reception_jd_tt": epoch,
        "requested_coordinate_flags": flags,
        "scope": base_scope,
        "geometric_returned_flags": int(geometric[1]),
        "initial_windows": initial_public,
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
    native: _NativeEphemeris,
    epoch: float,
    flags: int,
    invoke: NativeInvoker,
) -> SolarLightPathPolicy:
    """Retain app_pos_etc_sun's fixed observer and two exact Sun epochs.

    Public barycentric Sun calls also rebuild Earth as a native side effect.
    Rebuild both reception states before the original apparent request; never
    retain an Earth(t) from the file selected before the retarded Sun read.
    """
    states: dict[str, LightPathState] = {}
    policy: SolarLightPathPolicy = {
        "method_id": "owned_geocentric_solar_light_path_v1",
        "source_function": "sweph.c:app_pos_etc_sun",
        "reception_jd_tt": epoch,
        "requested_coordinate_flags": flags,
        "states": states,
        "scope": "Two exact retarded Sun evaluations and rebuilt reception observer in checked native source intervals; not an atomic read-set, derivative convergence or accuracy certificate.",
        "status": "pending",
    }
    unsupported = (
        native.FLG_TRUEPOS
        | native.FLG_BARYCTR
        | native.FLG_HELCTR
        | native.FLG_TOPOCTR
        | native.FLG_SPEED3
        | int(getattr(native, "FLG_CENTER_BODY", 1048576))
    )
    if flags & unsupported:
        policy["status"] = "not_applied"
        policy["reason"] = "unsupported_observer_position_or_three_epoch_speed"
        return policy
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
        at: float, body: int, barycentric: bool, label: str
    ) -> tuple[tuple[tuple[float, ...], int], _FileWindows | None]:
        requested = base | (native.FLG_BARYCTR if barycentric else 0)
        raw_result, observed = _post_call_endpoint_guard(
            native, "calc", (at, body, requested), {}, invoke
        )
        if not isinstance(raw_result, tuple) or len(raw_result) != 2:
            raise EphemerisSourceError("coordinate_contract_changed")
        values_seq, returned = raw_result
        if not isinstance(returned, int) or isinstance(returned, bool):
            raise EphemerisSourceError("coordinate_contract_changed")
        values = tuple(float(v) for v in values_seq)
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
        states[label] = {
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
        return (values, returned), observed

    def selected(observed: _FileWindows | None) -> _FileWindows:
        if observed is None or not _valid(observed):
            raise EphemerisSourceError("dependency_source_window_incoherent")
        if len({w[3] for w in observed}) != 1:
            raise EphemerisSourceError("edition_changed")
        return observed

    probe, observed = state(epoch, native.SUN, False, "initial_backend_probe")
    if not _is_swiss(native, probe):
        policy["status"] = "not_applied"
        policy["reason"] = "geometric_backend_not_swiss"
        return policy
    (earth, earth_flags), observed = state(
        epoch, native.EARTH, True, "initial_observer"
    )
    (sun, sun_flags), observed = state(epoch, native.SUN, True, "initial_sun")
    if not _is_swiss(native, (earth, earth_flags)) or not _is_swiss(
        native, (sun, sun_flags)
    ):
        raise EphemerisSourceError("model_changed")
    initial = selected(observed)
    policy["initial_windows"] = _public_windows(initial)

    def iterations(
        observer: tuple[float, ...],
        solar: tuple[float, ...],
        observed: _FileWindows | None,
        prefix: str,
    ) -> tuple[list[float] | None, _FileWindows | None]:
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
            windows = selected(observed)
            if not all(w[1] <= at <= epoch <= w[2] for w in windows):
                backend, observed = state(
                    at, native.SUN, False, prefix + f"_backend_{index}"
                )
                if not _is_swiss(native, backend):
                    return None, observed
            (solar, returned), observed = state(
                at, native.SUN, True, prefix + f"_sun_{index}"
            )
            if not _is_swiss(native, (solar, returned)):
                raise EphemerisSourceError("model_changed")
            epochs.append(at)
        return epochs, observed

    epochs, observed = iterations(earth, sun, observed, "selection")
    if epochs is None:
        policy["status"] = "restore_before_auxiliary_fallback"
        policy["reason"] = "retarded_auxiliary_backend_not_swiss"
        return policy
    common = selected(observed)
    if [w[3] for w in initial] != [w[3] for w in common] or not all(
        w[1] <= min(epochs) <= epoch <= w[2] for w in common
    ):
        raise EphemerisSourceError("dependency_source_window_incoherent")

    def reception(
        prefix: str,
    ) -> tuple[tuple[float, ...], tuple[float, ...], _FileWindows | None]:
        (earth, returned_earth), observed = state(
            epoch, native.EARTH, True, prefix + "_observer"
        )
        (sun, returned_sun), observed = state(epoch, native.SUN, True, prefix + "_sun")
        if not _is_swiss(native, (earth, returned_earth)) or not _is_swiss(
            native, (sun, returned_sun)
        ):
            raise EphemerisSourceError("model_changed")
        if selected(observed) != common:
            raise EphemerisSourceError("dependency_source_window_incoherent")
        return earth, sun, observed

    earth, sun, observed = reception("coherent")
    changed = initial != common
    if changed:
        refined, observed = iterations(earth, sun, observed, "refined")
        if (
            refined is None
            or selected(observed) != common
            or not all(w[1] <= min(refined) <= epoch <= w[2] for w in common)
        ):
            raise EphemerisSourceError("dependency_source_window_incoherent")
        reception("final")
    else:
        refined = epochs
    policy["status"] = "reselected_common_window" if changed else "already_covered"
    policy["selection_retarded_epochs_jd_tt"] = epochs
    policy["retarded_epochs_jd_tt"] = refined
    policy["selected_windows"] = _public_windows(common)
    return policy


def _planet_light_path(
    native: _NativeEphemeris,
    epoch: float,
    body: int,
    flags: int,
    invoke: NativeInvoker,
) -> PlanetLightPathPolicy:
    """Prepare the app_pos_etc_plan reception/retarded composite together.

    Called only after a fresh owned-context Sun preflight. The native two
    rough light-time iterations determine the dependency epoch; neither a
    residual nor a finite-difference estimate selects the source.
    """
    states: dict[str, LightPathState] = {}
    policy: PlanetLightPathPolicy = {
        "method_id": "owned_geocentric_planet_light_path_v1",
        "source_function": "sweph.c:app_pos_etc_plan",
        "body_id": body,
        "reception_jd_tt": epoch,
        "requested_coordinate_flags": flags,
        "auxiliary_coordinate_kind": "ICRF_cartesian_AU_and_AU_per_day",
        "scope": "Checked observed source intervals for a geocentric apparent planet light path; not an atomic native read-set, derivative convergence or accuracy certificate.",
        "states": states,
        "status": "pending",
    }
    unsupported = (
        native.FLG_TRUEPOS
        | native.FLG_BARYCTR
        | native.FLG_HELCTR
        | native.FLG_TOPOCTR
        | int(getattr(native, "FLG_CENTER_BODY", 1048576))
    )
    if flags & unsupported:
        policy["status"] = "not_applied"
        policy["reason"] = "not_supported_geocentric_apparent"
        return policy
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
    ) -> tuple[tuple[float, ...], int]:
        required_flags = base | (native.FLG_BARYCTR if barycentric else 0)
        raw_result, _ = _post_call_endpoint_guard(
            native, "calc", (at, target, required_flags), {}, invoke
        )
        if not isinstance(raw_result, tuple) or len(raw_result) != 2:
            raise EphemerisSourceError("coordinate_contract_changed")
        values_seq, returned = raw_result
        if not isinstance(returned, int) or isinstance(returned, bool):
            raise EphemerisSourceError("coordinate_contract_changed")
        values = tuple(float(v) for v in values_seq)
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
        states[label] = {
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

    def selected() -> _FileWindows:
        observed = _windows(native)
        if observed is None or not _valid(observed):
            raise EphemerisSourceError("dependency_source_window_incoherent")
        if len({w[3] for w in observed}) != 1:
            raise EphemerisSourceError("edition_changed")
        return observed

    def delay(target: tuple[float, ...], earth: tuple[float, ...]) -> float:
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
        policy["status"] = "not_applied"
        policy["reason"] = "geometric_backend_not_swiss"
        return policy
    target, _ = state(epoch, body, True, "initial_body")
    earth, _ = state(epoch, native.EARTH, True, "initial_observer")
    initial = selected()
    light_time = delay(target, earth)
    retarded = epoch - light_time
    policy["light_time_days"] = light_time
    policy["retarded_jd_tt"] = retarded
    policy["initial_windows"] = _public_windows(initial)
    if all(w[1] <= retarded <= epoch <= w[2] for w in initial):
        policy["status"] = "already_covered"
        policy["selected_windows"] = _public_windows(initial)
        return policy
    retarded_probe = state(retarded, body, False, "retarded_backend_probe", probe=True)
    if not _is_swiss(native, retarded_probe):
        policy["status"] = "restore_before_native_fallback"
        policy["reason"] = "retarded_geometric_backend_not_swiss"
        return policy
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
    policy["status"] = "reselected_common_window"
    policy["initial_light_time_days"] = light_time
    policy["selection_probe_jd_tt"] = retarded
    policy["light_time_days"] = refined
    policy["retarded_jd_tt"] = epoch - refined
    policy["selected_windows"] = _public_windows(common)
    return policy


def compressed_endpoint_call(
    native: _NativeEphemeris,
    operation: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    invoke: NativeInvoker,
    *,
    configured_path: Callable[[], str | None] = lambda: None,
) -> object:
    """Own caches only inside the explicit private-operation audit context.

    An earlier unwrapped call can leave target coefficients cached even after
    a Sun preflight or a nearby target replay. Clearing that state is necessary
    before source selection; a target's untrusted old result is not evaluated
    or invented for the receipt. No reset of an external caller's configuration.
    """
    state = _CONTEXT.get()
    audit = state.audit
    if operation in {"calc", "calc_ut"} and state.last_coordinate is not None:
        state = replace(state, last_coordinate=None)
        _CONTEXT.set(state)
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
    observer_sample = state.observer_sample
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
            or isinstance(flags, bool)
            or flags & required != required
            or flags & forbidden
        ):
            raise EphemerisSourceError("observer_source_window_incoherent")
    eligible = (
        operation in {"calc", "calc_ut"}
        and isinstance(body, int)
        and not isinstance(body, bool)
        and body in {*range(10), 14}
        and isinstance(instant, (int, float))
        and not isinstance(instant, bool)
        and math.isfinite(instant)
        and isinstance(flags, int)
        and not isinstance(flags, bool)
        and flags & _model_mask(native) in {0, native.FLG_SWIEPH}
        and str(getattr(native, "version", "unavailable")) == "2.10.03"
        and _cached_binding_version(native) == "2.10.3.2"
    )
    managed = audit is not None and state.dependency_context is None and eligible
    if not managed:
        dependent = state.dependency_context
        if dependent is not None and operation in {"calc", "calc_ut"}:
            if operation != "calc" or instant != dependent:
                raise EphemerisSourceError("dependency_source_window_incoherent")
        result, _ = _post_call_endpoint_guard(native, operation, args, kwargs, invoke)
        if (
            dependent is not None
            and operation == "calc"
            and not _is_swiss(native, result)
        ):
            raise EphemerisSourceError("model_changed")
        return result
    assert (
        audit is not None
        and isinstance(body, int)
        and isinstance(instant, (int, float))
        and isinstance(flags, int)
    )
    # The process owns these settings; set_ephe_path's cache/model reset must
    # never be applied to an arbitrary parent's configured native library.
    native.set_ephe_path(configured_path() or "")
    audit.resets += 1
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
        if not isinstance(probe, tuple) or len(probe) != 2:
            raise EphemerisSourceError("coordinate_model_changed")
        model_probe_flags = int(probe[1])
        if _is_swiss(native, probe):
            preflight_origin = native.FLG_BARYCTR
        elif model_probe_flags & _model_mask(native) != native.FLG_MOSEPH:
            raise EphemerisSourceError("coordinate_model_changed")
        native.set_ephe_path(configured_path() or "")
        audit.resets += 1
    preflight_flags = native.FLG_SWIEPH | native.FLG_TRUEPOS | preflight_origin
    _post_call_endpoint_guard(
        native,
        operation,
        (instant, native.SUN, preflight_flags),
        {},
        invoke,
    )
    solar: SolarLightPathPolicy | None = None
    lunar: LunarLightPathPolicy | None = None
    planet: PlanetLightPathPolicy | None = None
    if body == native.SUN:
        reception_tt = float(instant)
        if operation == "calc_ut":
            reception_tt += native.deltat_ex(reception_tt, native.FLG_SWIEPH)
        solar = _solar_light_path(native, reception_tt, flags, invoke)
        if solar["status"] == "restore_before_auxiliary_fallback":
            native.set_ephe_path(configured_path() or "")
            audit.resets += 1
            _post_call_endpoint_guard(
                native,
                operation,
                (instant, native.SUN, preflight_flags),
                {},
                invoke,
            )
            solar["status"] = "not_applied"
            solar["native_context_restarted"] = True
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
            audit.resets += 1
            _post_call_endpoint_guard(
                native,
                operation,
                (instant, native.SUN, preflight_flags),
                {},
                invoke,
            )
    result, observed = _post_call_endpoint_guard(
        native, operation, args, kwargs, invoke
    )
    if (
        not isinstance(result, tuple)
        or len(result) != 2
        or not isinstance(result[0], Sequence)
        or isinstance(result[0], (str, bytes))
        or not isinstance(result[1], int)
        or isinstance(result[1], bool)
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    if len(result[0]) != 6 or not all(math.isfinite(x) for x in result[0]):
        raise EphemerisSourceError("coordinate_values_unavailable")
    epoch = float(instant)
    if operation == "calc_ut":
        epoch += native.deltat_ex(epoch, result[1] & _model_mask(native))
        observed = (
            _windows(native)
            if _is_swiss(native, result) and _physical_slots(native, body, result[1])
            else None
        )
    windows = (
        _physical_windows(native, body, result[1], observed)
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
            or _public_windows(windows) != solar.get("selected_windows")
            or epoch != solar["reception_jd_tt"]
        ):
            raise EphemerisSourceError("dependency_source_window_incoherent")
    if planet is not None:
        if planet["status"] == "restore_before_native_fallback":
            if _is_swiss(native, result):
                raise EphemerisSourceError("dependency_source_window_incoherent")
            planet["status"] = "not_applied"
            planet["native_fallback_restarted"] = True
        elif planet["status"] in {"already_covered", "reselected_common_window"}:
            if not _is_swiss(native, result):
                raise EphemerisSourceError("model_changed")
            if (
                windows is None
                or not _valid(windows)
                or _public_windows(windows) != planet.get("selected_windows")
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
            or _public_windows(windows) != lunar.get("selected_windows")
            or epoch != lunar["reception_jd_tt"]
        ):
            raise EphemerisSourceError("lunar_source_window_incoherent")
    evidence: CoordinateContextEvidence = {
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
        "selected_windows": (
            _public_windows(windows) if windows is not None and _valid(windows) else []
        ),
        "physical_instant_shifted": False,
        "scope": "Requested target and frame after fresh private source preselection. The untrusted target state was not computed before resetting caches; no exact-preservation claim against that unknown state. Physical backend remains the returned model, including any declared fallback.",
    }
    if preflight_origin:
        evidence["preflight_requested_flags"] = preflight_flags
        evidence["preflight_reference_origin"] = (
            "barycentric" if preflight_origin & native.FLG_BARYCTR else "heliocentric"
        )
        evidence["preflight_establishes_geocentric_observer"] = False
        evidence["preflight_solar_vector_is_defined_zero"] = (
            preflight_origin == native.FLG_HELCTR
        )
        evidence["coordinate_reference_origin"] = (
            "barycentric"
            if result[1] & native.FLG_BARYCTR
            else (
                "heliocentric"
                if result[1] & native.FLG_HELCTR
                else ("topocentric" if result[1] & native.FLG_TOPOCTR else "geocentric")
            )
        )
        evidence["coordinate_is_defined_zero"] = not _physical_slots(
            native, body, result[1]
        )
        evidence["coordinate_represents_physical_body_vector"] = bool(
            _physical_slots(native, body, result[1])
        )
        if model_probe_flags is not None:
            evidence["preflight_model_probe"] = {
                "returned_flags": model_probe_flags,
                "coordinates_discarded": True,
                "native_context_reset_after_probe": True,
                "physical_source_certified": False,
            }
    if solar is not None:
        evidence["solar_light_path"] = solar
    if lunar is not None:
        evidence["lunar_light_path"] = lunar
    if planet is not None:
        evidence["planet_light_path"] = planet
    _CONTEXT.set(replace(_CONTEXT.get(), last_coordinate=evidence))
    return result


PATH_NAMES: dict[str, str] = {}


def _path_name(name: str) -> str:
    cached = PATH_NAMES.get(name)
    if cached is None:
        cached = Path(name).name
        PATH_NAMES[name] = cached
    return cached
