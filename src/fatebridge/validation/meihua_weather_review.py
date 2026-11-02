"""Replay a reviewed reader without rewriting a frozen study or its old gate."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Any

EXPECTED_BINDING_SHA256 = (
    "80a96762ad56ab05256ec8b6034ba122ecf8d78bc6f8b225c08cfb61173f3ecc"
)
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_ORIGINAL = {
    "meihua_weather_study.py": "d05071791a6be9ce3973d4d1f0f446c2d1bc714213b2e726d801233341ec8f54",
    "meihua_weather_references.py": "a344d5aa5667de698176ae8ca07ca43ad42b01ed7d412bee13b3dca9eb668166",
    "meihua_weather_reference_study.py": "a75d837aca6523c1593f5796f4c89977cda731b4fc0099da9eab3bd08eee2f6a",
}
_DEPENDENCIES = {
    *("validation/" + n for n in _ORIGINAL),
    "core/meihua_clock_iso.py",
    "validation/meihua_source_guard.py",
    "validation/meihua_runtime_guard.py",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _json(raw: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate review/material JSON keys")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique)


def _portable_tree(value: Any) -> Any:
    if isinstance(value, ast.AST):
        fields = []
        for key in value._fields:
            item = getattr(value, key, None)
            if key == "type_params":
                if item:
                    raise ValueError("Nonempty type parameters require a new review")
                continue
            fields.append([key, _portable_tree(item)])
        return {"node": type(value).__name__, "fields": fields}
    if isinstance(value, list):
        return [_portable_tree(v) for v in value]
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if value is Ellipsis:
        return {"ellipsis": True}
    return value


def _ast_digest(node: ast.AST) -> str:
    return _sha(_canonical(_portable_tree(node)))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    found = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(found) != 1:
        raise ValueError("A reviewed function must be present exactly once")
    return found[0]


def load_review_binding() -> dict[str, Any]:
    raw = (
        files("fatebridge.data")
        .joinpath("meihua/weather-reference-review-v1.json")
        .read_bytes()
    )
    if _sha(raw) != EXPECTED_BINDING_SHA256:
        raise ValueError("Weather review binding changed; renewed review is required")
    result: dict[str, Any] = _json(raw)
    if (
        result["id"] != "meihua_weather_reference_review_v1"
        or result["version"] != "1.0.0"
    ):
        raise ValueError("Unknown weather review identity")
    return result


class _UndoClock(ast.NodeTransformer):
    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module == "fatebridge.core.meihua_clock_iso":
            if (
                node.level != 0
                or len(node.names) != 1
                or node.names[0].name != "parse_meihua_clock_label"
                or node.names[0].asname is not None
            ):
                raise ValueError("Unreviewed timestamp import")
            return None
        return node

    def visit_Call(self, node: ast.Call) -> ast.Call:
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "parse_meihua_clock_label"
        ):
            node.func = ast.Attribute(
                value=ast.Name(id="datetime", ctx=ast.Load()),
                attr="fromisoformat",
                ctx=ast.Load(),
            )
        return node


def verify_reviewed_implementation(review: dict[str, Any], package: Path) -> None:
    """Require bytes AND reviewed AST scope; updating a file hash is insufficient."""
    package = package.resolve(strict=True)
    if set(review["current_package_files"]) != _DEPENDENCIES:
        raise ValueError("The complete reviewed dependency set is required")
    if review["original_source_sha256"] != _ORIGINAL or set(
        review["original_source_texts"]
    ) != set(_ORIGINAL):
        raise ValueError("Original weather implementation references changed")
    current = {}
    for name, expected in review["current_package_files"].items():
        path = (package / name).resolve(strict=True)
        if not path.is_relative_to(package) or _sha(path.read_bytes()) != expected:
            raise ValueError("Current weather implementation bytes need renewed review")
        current[name] = ast.parse(path.read_text())
    for name, functions in review["reviewed_function_AST"].items():
        for function, expected in functions.items():
            if _ast_digest(_function(current[name], function)) != expected:
                raise ValueError("Reviewed function AST changed")
    for name, constants in review["reviewed_constant_AST"].items():
        for constant, expected in constants.items():
            found = [
                n
                for n in current[name].body
                if isinstance(n, ast.Assign)
                and any(isinstance(k, ast.Name) and k.id == constant for k in n.targets)
            ]
            if len(found) != 1 or _ast_digest(found[0]) != expected:
                raise ValueError("Reviewed constant AST changed")
    for name, expected in review["reviewed_dependency_module_AST"].items():
        if _ast_digest(current[name]) != expected:
            raise ValueError("Reviewed dependency module AST changed")
    for name, expected in _ORIGINAL.items():
        text = review["original_source_texts"][name]
        if _sha(text.encode()) != expected:
            raise ValueError("Frozen original weather source bytes changed")
        original = ast.parse(text)
        if (
            _ast_digest(original)
            != review["original_module_AST"][name]["original_module_ast_sha256"]
        ):
            raise ValueError("Original module AST binding changed")
        normalized = _UndoClock().visit(copy.deepcopy(current["validation/" + name]))
        if name == "meihua_weather_study.py":
            normalized.body = [
                n
                for n in normalized.body
                if not (
                    isinstance(n, ast.Assign)
                    and any(
                        isinstance(k, ast.Name) and k.id == "_TRACE_DEFINITIONS"
                        for k in n.targets
                    )
                )
            ]
            normalized.body = [
                (
                    copy.deepcopy(_function(original, "parse_hko_rainfall"))
                    if isinstance(n, ast.FunctionDef) and n.name == "parse_hko_rainfall"
                    else n
                )
                for n in normalized.body
            ]
        if name == "meihua_weather_reference_study.py":
            kernel = _function(normalized, "_evaluate_reference_material")
            entry = _function(normalized, "audit_weather_reference_study")
            last = entry.body[-1]
            if not (
                isinstance(last, ast.Return)
                and isinstance(last.value, ast.Call)
                and isinstance(last.value.func, ast.Name)
                and last.value.func.id == "_evaluate_reference_material"
                and len(last.value.args) == 1
                and isinstance(last.value.args[0], ast.Name)
                and last.value.args[0].id == "base"
                and not last.value.keywords
            ):
                raise ValueError("Reference kernel extraction boundary changed")
            entry.body = entry.body[:-1] + kernel.body
            normalized.body.remove(kernel)
        if _ast_digest(normalized) != _ast_digest(original):
            raise ValueError(
                "Unreviewed weather policy, scoring or source logic changed"
            )


def _capture_material(directory: Path, review: dict[str, Any]) -> dict[str, bytes]:
    base = directory.resolve(strict=True)
    captured = {}
    for name, expected in review["original_material_files"].items():
        path = (base / name).resolve(strict=True)
        if not path.is_relative_to(base):
            raise ValueError("Original study material escapes its directory")
        raw = path.read_bytes()
        if _sha(raw) != expected:
            raise ValueError(
                "Frozen original study, source, plan or evaluation changed"
            )
        captured[name] = raw
    lock = _json(captured["reference-lock.json"])
    if lock["implementation_files"] != _ORIGINAL:
        raise ValueError("Original strict implementation references changed")
    if _sha(captured["reference-lock.json"]) != review["original_lock_sha256"]:
        raise ValueError("Original strict lock bytes changed")
    return captured


def audit_reviewed_weather_reference(directory: Path) -> dict[str, Any]:
    """Require full original output equality; this never certifies prediction skill."""
    from fatebridge.validation.meihua_runtime_guard import (
        capture_calendar_runtime,
        verify_calendar_runtime,
    )
    from fatebridge.validation.meihua_source_guard import (
        capture_package_sources,
        verify_package_sources,
    )

    package = PACKAGE_ROOT.resolve(strict=True)
    source = capture_package_sources(package)
    runtime = capture_calendar_runtime()
    review = load_review_binding()
    verify_reviewed_implementation(review, package)
    material = _capture_material(Path(directory), review)
    from fatebridge.validation.meihua_weather_reference_study import (
        _evaluate_reference_material,
        audit_weather_reference_study,
    )
    from fatebridge.validation.meihua_weather_study import parse_hko_rainfall

    # A private byte copy prevents a mutable caller path from being re-read later.
    with tempfile.TemporaryDirectory(
        prefix="fatebridge-weather-reviewed-"
    ) as temporary:
        private = Path(temporary).resolve(strict=True)
        for name, raw in material.items():
            path = private / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        try:
            audit_weather_reference_study(private)
        except ValueError as error:
            strict_error = str(error)
            if strict_error != "Locked reference source or protocol changed":
                raise
        else:
            raise ValueError(
                "Reviewed replay must not relabel the original strict gate"
            )
        start, end = date(1991, 1, 1), date(2026, 10, 1)
        observations = parse_hko_rainfall(
            material["sources/daily_HKO_RF_ALL.csv"], start=start, end=end
        )
        rows = []
        day = start
        while day < end:
            value = observations.get(day)
            rows.append(
                {
                    "date": day.isoformat(),
                    "source_value": value.raw_value if value else None,
                    "source_completeness": value.completeness if value else None,
                    "expected_rain_ge0_1_mm": (
                        value.occurred(Decimal("0.1")) if value else None
                    ),
                }
            )
            day += timedelta(days=1)
        if (
            len(observations) != 13057
            or len(rows) != review["source_rows"]
            or _sha(_canonical(rows))
            != review["independent_source_rows_canonical_sha256"]
        ):
            raise ValueError("Complete frozen source-row interpretation differs")
        replay = _evaluate_reference_material(private)
        expected = _json(material["evaluation.json"])
        if _sha(_canonical(expected)) != review[
            "original_full_report_canonical_sha256"
        ] or _canonical(replay) != _canonical(expected):
            raise ValueError(
                "The complete original report must reproduce without projection"
            )
    load_review_binding()
    verify_reviewed_implementation(review, package)
    verify_package_sources(package, source)
    verify_calendar_runtime(runtime)
    return {
        "review_id": review["id"],
        "review_binding_sha256": EXPECTED_BINDING_SHA256,
        "reviewed_replay_integrity": "passed",
        "original_strict_binding_gate_met": False,
        "original_strict_binding_error": strict_error,
        "original_lock_rewritten": False,
        "current_package_files": review["current_package_files"],
        "original_source_sha256": dict(_ORIGINAL),
        "source_rows_compared": len(rows),
        "complete_original_report_canonical_sha256": review[
            "original_full_report_canonical_sha256"
        ],
        "complete_original_report_equal": True,
        "forecast_records_retained": replay["original_forecast_records_retained"],
        "unique_target_dates_retained": replay["unique_target_dates"],
        "original_primary_endpoint": replay["old_primary_endpoint"],
        "original_primary_gate_met": replay["old_primary_endpoint"][
            "passes_full_cohort_baselines"
        ],
        "replay": replay,
        "source_guard": source,
        "runtime_guard": runtime,
        "new_real_outcomes": 0,
        "new_forecasts": 0,
        "independent_model_evaluations": 0,
        "external_expert_review_or_origin_authentication": False,
        "fresh_process_and_immutable_snapshot_required": True,
        "actual_full_dependency_readset_authenticated": False,
        "original_prediction_gate_changed": False,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
