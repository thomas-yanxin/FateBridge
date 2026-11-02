"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import hashlib
import math
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, NoReturn, TypeGuard

from fatebridge.utils.errors import EphemerisSourceError

RULESET = "fatebridge.observed_physical_data_policy.v1"


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise EphemerisSourceError("required_data_files_unavailable") from error
    return digest.hexdigest()


@dataclass
class DataFilePolicy:
    failure: str | None = None
    physical_calls_by_model: dict[str, int] = field(default_factory=dict)
    nonphysical_calls: int = 0
    reference_zero_calls: int = 0
    event_endpoint_probes: int = 0
    files: dict[Path, str] = field(default_factory=dict)
    worker_reports: list[dict[str, Any]] = field(default_factory=list)

    def fail(self, reason: str) -> NoReturn:
        self.failure = self.failure or reason
        raise EphemerisSourceError(self.failure)

    def observe_file(self, path: Path) -> None:
        if path not in self.files:
            self.files[path] = _digest(path)

    def finish(self) -> None:
        if self.failure:
            raise EphemerisSourceError(self.failure)
        for path, digest in self.files.items():
            if _digest(path) != digest:
                self.fail("changed_during")

    def receipt(self) -> dict[str, Any]:
        return {
            "ruleset_id": RULESET,
            "requested": "require_data_files",
            "physical_calls_by_model": dict(self.physical_calls_by_model),
            "analytical_or_nonphysical_calls": self.nonphysical_calls,
            "reference_zero_calls": self.reference_zero_calls,
            "event_endpoint_probes": self.event_endpoint_probes,
            "observed_file_path_count": len(self.files),
            "observed_files": [
                {"filename": filename, "sha256": digest}
                for filename, digest in sorted(
                    {(path.name, digest) for path, digest in self.files.items()}
                )
            ],
            "private_worker_reports": list(self.worker_reports),
            "scope": "Observed physical calc/calc_ut results and orbital-model fallbacks throughout this request, including clock and sample calls. Native rise/set query and returned event epochs are separately probed; solver-internal reads/evaluations are not observable. Analytical points, fictitious elements, reference zeros and Earth-rotation models are separate.",
            "atomic_native_read_set_proven": False,
            "all_native_event_internal_models_verified": False,
            "accuracy_certified": False,
        }


_POLICY: ContextVar[DataFilePolicy | None] = ContextVar(
    "physical_data_file_policy", default=None
)


def current_policy() -> DataFilePolicy | None:
    return _POLICY.get()


def policy_mode() -> str:
    return "require_data_files" if current_policy() is not None else "auto"


def require_physical_model(model: str) -> None:
    state = current_policy()
    if state is not None and model not in {"swieph", "jpl"}:
        state.fail("required_data_files_fallback")


def _physical(body: Any) -> TypeGuard[int]:
    return (
        isinstance(body, int)
        and body >= 0
        and body not in {10, 11, 12, 13, 21, 22}
        and not 40 <= body < 1000
    )


def _coordinate_result(
    native: Any,
    operation: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    value: Any,
    model_from_retflag: Callable[[int], str],
) -> Any:
    state = current_policy()
    if state is None:
        return value
    body = args[1] if len(args) > 1 else kwargs.get("planet")
    if not _physical(body):
        state.nonphysical_calls += 1
        return value
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not isinstance(value[1], int)
        or value[1] < 0
    ):
        state.fail("required_data_files_unavailable")
    coordinates, flags = value
    from fatebridge.core.compressed_ephemeris import _physical_slots

    slots = _physical_slots(native, body, flags)
    if not slots:
        if len(coordinates) != 6 or any(value != 0 for value in coordinates):
            state.fail("coordinate_values_unavailable")
        state.reference_zero_calls += 1
        return value
    model = model_from_retflag(flags)
    require_physical_model(model)
    if len(coordinates) != 6 or not all(math.isfinite(v) for v in coordinates):
        state.fail("coordinate_values_unavailable")
    getter = getattr(native, "get_current_file_data", None)
    if not callable(getter):
        state.fail("required_data_files_unverified")
    if model == "swieph":
        from importlib.metadata import version

        from fatebridge.core.astro.native_identity import binding_distribution_version

        if (
            str(getattr(native, "version", "unavailable")),
            binding_distribution_version(native, version),
        ) != ("2.10.03", "2.10.3.2"):
            state.fail("required_data_files_unverified")
        instant = (
            args[0] if args else kwargs.get("tjdet" if operation == "calc" else "tjdut")
        )
        if not isinstance(instant, (int, float)) or not math.isfinite(instant):
            state.fail("required_data_files_unverified")
        epoch = float(instant)
        if operation == "calc_ut":
            epoch += native.deltat_ex(epoch, flags & 7)
        if 15 <= body <= 20 or body >= 10000:
            slots = (*slots, 2)
        for slot in slots:
            path, start, end, _ = getter(slot)
            if (
                not path
                or not math.isfinite(start)
                or not math.isfinite(end)
                or not start <= epoch <= end
                or start >= end
            ):
                state.fail("required_data_files_unverified")
            state.observe_file(Path(path).absolute())
    else:
        path = getter(0)[0]
        if not path:
            state.fail("required_data_files_unverified")
        state.observe_file(Path(path).absolute())
    state.physical_calls_by_model[model] = (
        state.physical_calls_by_model.get(model, 0) + 1
    )
    return value


@contextmanager
def native_call_policy(
    native: Any,
    operation: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    probe_call: Callable[..., Any],
    model_from_retflag: Callable[[int], str],
) -> Iterator[Callable[[Any], Any]]:
    state = current_policy()
    if state is None:
        yield lambda value: value
        return
    body = args[1] if len(args) > 1 else kwargs.get("planet")
    coordinate = operation in {"calc", "calc_ut"}
    event = operation == "rise_trans"
    if (
        coordinate
        and _physical(body)
        and not callable(getattr(native, "get_current_file_data", None))
    ):
        state.fail("required_data_files_unverified")

    def probe(epoch: float) -> None:
        probe_call("calc_ut", epoch, body, native.FLG_SWIEPH | native.FLG_SPEED)
        state.event_endpoint_probes += 1

    def observe(value: Any) -> Any:
        if coordinate:
            return _coordinate_result(
                native, operation, args, kwargs, value, model_from_retflag
            )
        if event and value[0] >= 0:
            probe(float(value[1][0]))
        return value

    try:
        if event:
            if not _physical(body):
                state.fail("required_data_files_unverified")
            probe(float(args[0] if args else kwargs["tjdut"]))
        yield observe
    except EphemerisSourceError as error:
        state.failure = state.failure or error.reason
        raise
    except Exception as error:
        if coordinate and _physical(body) or event:
            state.fail("required_data_files_unavailable")
        raise


def merge_worker_policy(receipt: Any) -> None:
    state = current_policy()
    if state is not None:
        if (
            not isinstance(receipt, dict)
            or receipt.get("ruleset_id") != RULESET
            or receipt.get("requested") != "require_data_files"
        ):
            state.fail("required_data_files_unverified")
        state.worker_reports.append(receipt)
