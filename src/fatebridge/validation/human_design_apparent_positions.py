"""Replay observed batch geometry and bind it to the original nominal sides.

No ephemeris is recalculated. Original receipt custody is still required;
latitude and distance are supplied native observations, not independent truth.
"""

import json
import math
from typing import Any

from fatebridge.core.astro.reference import PHYSICAL_BODIES
from fatebridge.core.human_design_apparent_positions import build_context
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.validation.claims import _same_value


def checked_context(payload: dict[str, Any]) -> dict[str, Any]:
    context = payload["apparent_position_context"]
    batches = context["batches"]
    refs = context["nominal_side_batch_ids"]
    if (
        not isinstance(batches, list)
        or not batches
        or set(refs) != {"personality", "design"}
    ):
        raise ValueError("Missing position batch or nominal side")
    observed: dict[tuple[str, str, str], list[Any]] = {}
    seen = set()
    raw_batches = []
    for index, batch in enumerate(batches):
        raw = {
            k: batch[k]
            for k in (
                "id",
                "jd_tt",
                "node_mode",
                "requested_backend",
                "source_role",
                "bodies",
                "observed_count",
            )
        }
        tt, count = raw["jd_tt"], raw["observed_count"]
        if (
            raw["id"] != f"batch_{index}"
            or type(tt) is not float
            or not math.isfinite(tt)
            or type(count) is not int
            or count < 1
            or raw["node_mode"] not in {"true", "mean"}
            or raw["requested_backend"] not in {"swieph", "moshier"}
            or raw["source_role"] not in {"activation", "root_bracket_activation"}
            or not 1 <= len(raw["bodies"]) <= 10
            or [r["body"] for r in raw["bodies"]]
            != list(PHYSICAL_BODIES[: len(raw["bodies"])])
        ):
            raise ValueError("Malformed native batch")
        key = json.dumps(
            {k: v for k, v in raw.items() if k not in {"id", "observed_count"}},
            sort_keys=True,
            allow_nan=False,
        )
        if key in seen:
            raise ValueError("Undeduplicated position batch")
        seen.add(key)
        for row in raw["bodies"]:
            coords = row["native_coordinates"]
            if (
                set(row)
                != {"body", "native_coordinates", "return_flags", "ephemeris_model"}
                or not isinstance(coords, list)
                or len(coords) != 4
            ):
                raise ValueError("Malformed native coordinates")
            if any(
                type(coords[k]) is not float or not math.isfinite(coords[k])
                for k in (0, 3)
            ):
                raise ValueError("Invalid longitude or speed")
            if any(
                not (
                    (type(x) is float and math.isfinite(x))
                    or (type(x) is str and x in {"nan", "inf", "-inf"})
                )
                for x in coords[1:3]
            ):
                raise ValueError("Invalid supplementary observation encoding")
            model = position_flag_model(row["return_flags"])
            if row["ephemeris_model"] != model or (
                raw["requested_backend"] == "moshier" and model != "moshier"
            ):
                raise ValueError("Wrong batch backend")
            context_key = row["body"], raw["source_role"], model
            total = observed.setdefault(context_key, [0, tt, tt])
            total[0] += count
            total[1] = min(total[1], tt)
            total[2] = max(total[2], tt)
        raw_batches.append(raw)
    source_totals: dict[tuple[str, str, str], list[Any]] = {}
    for row in payload["ephemeris_source_evidence"]["contexts"]:
        if row["body"] not in PHYSICAL_BODIES or row["role"] == "solar_root":
            continue
        source_key = row["body"], row["role"], row["native_return_flag_model"]
        lo, hi = row["minimum_jd_tt"], row["maximum_jd_tt"]
        total = source_totals.setdefault(source_key, [0, lo, hi])
        total[0] += row["observed_evaluation_count"]
        total[1], total[2] = min(total[1], lo), max(total[2], hi)
    if not _same_value(observed, source_totals):
        raise ValueError(
            "Position batches do not account for existing source observations"
        )
    lookup = {b["id"]: b for b in raw_batches}
    for side in ("personality", "design"):
        batch = lookup[refs[side]]
        if (
            len(batch["bodies"]) != 10
            or batch["source_role"] != "activation"
            or batch["node_mode"] != payload["calculation_policy"]["node_mode"]
            or not _same_value(batch["jd_tt"], payload["time_scales"][side]["jd_tt"])
        ):
            raise ValueError("Nominal side TT or policy mismatch")
        activations = {r["body"]: r for r in payload["activations"][side]}
        for row in batch["bodies"]:
            actual = activations[row["body"]]
            expected = {
                "longitude": row["native_coordinates"][0] % 360.0,
                "longitude_speed": row["native_coordinates"][3],
                "return_flags": row["return_flags"],
                "ephemeris_model": row["ephemeris_model"],
            }
            if any(not _same_value(actual[k], v) for k, v in expected.items()):
                raise ValueError(
                    "Nominal activation not from its declared native batch"
                )
    expected = build_context(raw_batches, refs)
    if not _same_value(context, expected):
        raise ValueError("Apparent position geometry or declared scope mismatch")
    return expected
