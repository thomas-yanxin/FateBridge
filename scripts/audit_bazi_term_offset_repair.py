"""Replay all frozen ambiguous clocks and the complete UTC control cohort."""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from scripts.audit_bazi_term_offsets import (
    FIXTURE,
    ROOT,
    baseline_class,
    digest,
    inputs,
)

DISCOVERY = ROOT / "docs/validation/bazi-term-offset-discovery-first-v1.json.gz"
NEW_FIELDS = {"datetime_with_offset", "utc_offset_seconds", "fold", "timezone"}


def audit() -> dict[str, Any]:
    protocol, archive, metadata, zones = inputs()
    if digest(DISCOVERY) != Path(str(DISCOVERY) + ".sha256").read_text().strip():
        raise ValueError("First discovery changed")
    first = json.loads(gzip.decompress(DISCOVERY.read_bytes()))
    if first["scanned_pairs"] != protocol["cohort"]["cartesian_pairs"]:
        raise ValueError("First discovery omitted part of the cohort")
    before, functions = baseline_class()
    from fatebridge.core.almanac import SolarTerm, get_day_ganzhi
    from fatebridge.core.output_chinese import SolarTerm as OutputTerm

    current_ast = ast.parse((ROOT / "src/fatebridge/core/almanac.py").read_text())
    actual_functions = {
        n.name: ast.dump(n, include_attributes=False)
        for n in current_ast.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if actual_functions["get_day_ganzhi"] != functions["get_day_ganzhi"]:
        raise ValueError("Top-level calendar numerical functions changed")
    source_rows = {(r["year"], r["index"]): r for r in archive["rows"]}
    rows = []

    def compare(
        record: dict[str, Any],
        zone_name: str,
        zone: Any,
        old_record: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        instant = datetime.fromisoformat(record["public_civil_datetime"]).astimezone(
            timezone.utc
        )
        local = instant.astimezone(zone)
        args = (
            record["name"],
            local,
            local.strftime("%Y%m%d"),
            get_day_ganzhi(local.year, local.month, local.day),
            record["actual_provider"],
            record["actual_model"],
        )
        old = before(*args, solar_model_details=record["details"]).as_dict()
        current = SolarTerm(*args, solar_model_details=record["details"]).as_dict()
        if old_record is not None and old != old_record:
            raise ValueError("Original counterexample serialized fields changed")
        if {k: v for k, v in current.items() if k not in NEW_FIELDS} != old:
            raise ValueError("A legacy serialized value changed")
        parsed = datetime.fromisoformat(current["datetime_with_offset"])
        if parsed.astimezone(timezone.utc) != instant:
            raise ValueError("Aware clock does not preserve supplied instant")
        offset = local.utcoffset()
        if offset is None:
            raise ValueError("Pinned aware clock has no offset")
        if (
            current["fold"] != local.fold
            or current["utc_offset_seconds"] != offset.total_seconds()
        ):
            raise ValueError("Fold or offset metadata differs from supplied clock")
        OutputTerm.model_validate(current)
        return {
            "year": record["year"],
            "index": record["index"],
            "name": record["name"],
            "zone": zone_name,
            "record": current,
            "roundtrip_civil_offset_label": parsed.astimezone(timezone.utc).isoformat(),
            "roundtrip_error_seconds": (
                parsed.astimezone(timezone.utc) - instant
            ).total_seconds(),
            "legacy_values_preserved": True,
        }

    for row in first["rows"]:
        value = compare(
            source_rows[(row["year"], row["index"])],
            row["zone"],
            zones[row["zone"]],
            row["legacy_record"],
        )
        value["original_legacy_error_seconds"] = row[
            "legacy_reconstruction_error_seconds"
        ]
        rows.append(value)
    controls = [compare(row, "UTC", timezone.utc) for row in archive["rows"]]
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "first_discovery_sha256": digest(DISCOVERY),
        "current_almanac_sha256": digest(ROOT / "src/fatebridge/core/almanac.py"),
        "current_output_contract_sha256": digest(
            ROOT / "src/fatebridge/core/output_chinese.py"
        ),
        "original_cartesian_pairs": first["scanned_pairs"],
        "ambiguous_rows": len(rows),
        "utc_control_rows": len(controls),
        "all_ambiguous_cases_retained": len(rows) == first["ambiguous_rows"],
        "original_legacy_failures_retained": first["legacy_reconstruction_failures"],
        "new_roundtrip_failures": 0,
        "maximum_new_roundtrip_error_seconds": 0,
        "all_legacy_serialized_values_preserved": True,
        "calendar_top_level_function_asts_unchanged": actual_functions == functions,
        "historical_almanac_original_hash_verified": True,
        "live_day_ganzhi_function_ast_unchanged": True,
        "rows": rows,
        "utc_controls": controls,
        "scope": "Serialization of existing actual timestamps, not a fresh solar solver accuracy trial, absolute UTC certification or future timezone-law validation.",
        "lossless_delivery_component_passed": True,
        "original_one_second_tt_threshold_changed": False,
        "original_native_moshier_failures_superseded": False,
        "real_world_predictive_validity": "not_tested",
        "new_model_executions": 0,
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    checksum = Path(str(output) + ".sha256")
    if output.exists() or checksum.exists():
        raise SystemExit("Output exists; preserve first results")
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    checksum.write_text(digest(output) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "ambiguous_rows",
                    "utc_control_rows",
                    "original_legacy_failures_retained",
                    "new_roundtrip_failures",
                    "calendar_top_level_function_asts_unchanged",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
