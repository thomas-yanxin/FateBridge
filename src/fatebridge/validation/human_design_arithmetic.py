"""Finite opposition probes; conditional arithmetic is not ephemeris truth."""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from importlib.resources import files
from typing import Any

from fatebridge.core.human_design_mechanics import (
    longitude_activation,
    opposite_activation,
)

LEVELS = ("gate", "line", "color", "tone", "base")


def check_opposition_arithmetic() -> dict[str, Any]:
    source_bytes = (
        files("fatebridge.data")
        .joinpath("human_design/rave-2001-reference.json")
        .read_bytes()
    )
    # Read the gate ordering from the separately frozen primary table, not the
    # implementation constant. The printed 29.1/29.2 disagreement remains;
    # this particular check explicitly tests the declared uniform subdivisions.
    reference = json.loads(source_bytes)
    gates = [
        r["gate"]
        for r in sorted(
            reference["gates"], key=lambda r: (r["start_longitude"] - 302) % 360
        )
    ]
    if len(gates) != 64 or set(gates) != set(range(1, 65)):
        raise ValueError("Primary gate reference is incomplete")
    checked = current_wrong = legacy_wrong = 0
    current_counts = dict.fromkeys(LEVELS, 0)
    legacy_counts = dict.fromkeys(LEVELS, 0)
    examples: dict[str, Any] = {}
    for index in range(69120):
        boundary = float((Fraction(302) + Fraction(index, 192)) % 360)
        for direction in (-math.inf, math.inf):
            source = math.nextafter(boundary, direction)
            if not 0 <= source < 360:
                continue
            coordinate = (Fraction(source) + 180 - 302) % 360
            gate_index, within = divmod(coordinate, Fraction(45, 8))
            line_index, within = divmod(within, Fraction(15, 16))
            color_index, within = divmod(within, Fraction(5, 32))
            tone_index, within = divmod(within, Fraction(5, 192))
            base_index = within // Fraction(1, 192)
            expected = dict(
                zip(
                    LEVELS,
                    [
                        gates[int(gate_index)],
                        *(
                            int(i) + 1
                            for i in (line_index, color_index, tone_index, base_index)
                        ),
                    ],
                )
            )
            current = opposite_activation(source)
            legacy = longitude_activation((source + 180.0) % 360.0)
            old_diff = [k for k in LEVELS if legacy[k] != expected[k]]
            new_diff = [k for k in LEVELS if current[k] != expected[k]]
            legacy_wrong += bool(old_diff)
            current_wrong += bool(new_diff)
            for level in LEVELS:
                legacy_counts[level] += level in old_diff
                current_counts[level] += level in new_diff
                if level in old_diff and level not in examples:
                    examples[level] = {
                        "source_longitude": source,
                        "source_hex": source.hex(),
                        "legacy_display": legacy["longitude"],
                        "current_display": current["longitude"],
                        "expected": expected,
                        "legacy": {k: legacy[k] for k in LEVELS},
                        "current": {k: current[k] for k in LEVELS},
                    }
            checked += 1
    return {
        "method_id": "human_design_exact_opposition_arithmetic_v1",
        "status": (
            "declared_arithmetic_probes_passed"
            if checked == 138239 and current_wrong == 0
            else "failed"
        ),
        "probes_checked": checked,
        "current_wrong_probes": current_wrong,
        "current_wrong_by_level": current_counts,
        "legacy_wrong_probes": legacy_wrong,
        "legacy_wrong_by_level": legacy_counts,
        "representative_legacy_failures": examples,
        "primary_gate_reference_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "sampling_plan": "Both immediate binary-float neighbors of each uniform rational Base boundary, restricted to 0 <= source < 360; declared count 138239. No epsilon or tolerance shifts a sector.",
        "scope": "Synthetic arithmetic probes conditional on supplied binary floats and the declared uniform divisions. Does not measure real-birth error frequency, certify source ephemeris precision, resolve printed 29.1/29.2, or accept a complete original text.",
    }
