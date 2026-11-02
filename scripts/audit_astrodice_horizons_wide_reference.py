"""Independently replay raw TT/JD identities and wide-reference derivatives."""

import argparse
import csv
import hashlib
import io
import json
import math
import re
from datetime import date, datetime
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from scripts.astrodice_reference_math import (
    COMPONENT_ULP_BUDGET,
    PRECISION,
    check_stored_direction,
    precise_direction,
)

DAY_US = 86400000000
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_tick(label):
    match = re.fullmatch(
        r"(\d+)(ad|bc)-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{6})", label
    )
    if match is None:
        raise ValueError("TT input lost its explicit calendar era")
    y, era, m, d, h, mi, s, us = match.groups()
    if int(y) < 1:
        raise ValueError("BC/AD labeling has no year zero")
    y = int(y) if era == "ad" else 1 - int(y)
    cycle, remainder = divmod(y - 1, 400)
    ordinal = date(remainder + 1, MONTHS.index(m) + 1, int(d)).toordinal()
    ordinal += 146097 * cycle
    h, mi, s, us = map(int, (h, mi, s, us))
    if h >= 24 or mi >= 60 or s >= 60:
        raise ValueError("Invalid reference clock")
    return ordinal * DAY_US + ((h * 60 + mi) * 60 + s) * 1000000 + us


def center_tick(label):
    dt = datetime.fromisoformat(label)
    return dt.toordinal() * DAY_US + (
        ((dt.hour * 60 + dt.minute) * 60 + dt.second) * 1000000 + dt.microsecond
    )


def interpolation_weights():
    # Solve the polynomial moment system, independently of the collector's
    # closed factorial formula. Nodes0,±1,...,±6 and degrees0..12 are exact.
    nodes = list(range(-6, 7))
    a = [
        [Fraction(x**power) for x in nodes] + [Fraction(power == 1)]
        for power in range(13)
    ]
    for col in range(13):
        pivot = next(i for i in range(col, 13) if a[i][col])
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        a[col] = [v / factor for v in a[col]]
        for row in range(13):
            if row == col:
                continue
            factor = a[row][col]
            a[row] = [v - factor * u for v, u in zip(a[row], a[col])]
    weights = dict(zip(nodes, (row[-1] for row in a)))
    if any(
        sum(weights[x] * x**power for x in nodes) != int(power == 1)
        for power in range(13)
    ):
        raise ValueError("Reference stencil moment identity failed")
    return weights


def validate(protocol_path, reference_path, material, seal_path):
    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    seal = json.loads(seal_path.read_text())
    if (
        digest(reference_path) != seal["reference_sha256"]
        or digest(protocol_path) != seal["protocol_sha256"]
        or reference["protocol_sha256"] != digest(protocol_path)
        or reference["candidate_imported"]
        or reference["Swiss_imported"]
    ):
        raise ValueError("Frozen independent source identity changed")
    point_map = {}
    raw_failures = []
    auxiliary_batches_validated = 0
    entries = [
        json.loads(s) for s in (material / "requests.jsonl").read_text().splitlines()
    ]
    batches = {b["batch"]: b for b in reference["batches"]}
    for entry in entries:
        body = entry["body"]
        params = entry["parameters"]
        anchored = batches.get(entry["batch"])
        if (
            anchored is None
            or anchored["body"] != body
            or anchored["parameters"] != params
        ):
            raise ValueError("Request journal differs from immutable reference batch")
        if any(params.get(k) != v for k, v in protocol["reference_parameters"].items()):
            raise ValueError("Reference parameter contract changed")
        if params["COMMAND"] != f"'{protocol['targets'][body]}'":
            raise ValueError("Reference target changed")
        labels = re.findall(r"'([^']+)'", params["TLIST"])
        if params["TLIST_TYPE"] in {"'JD'", "'MJD'"}:
            requested = []
            for value in labels:
                # Invert the declared encoding with independent exact
                # rational arithmetic, not the collector's decimal formatter.
                day_zero = (
                    Fraction(-678576)
                    if params["TLIST_TYPE"] == "'MJD'"
                    else Fraction(3442849, 2)
                )
                exact_tick = (Fraction(value) - day_zero) * DAY_US
                nearest = round(exact_tick)
                if abs(exact_tick - nearest) > Fraction(1, 10**30):
                    raise ValueError("JD input label changed the requested microsecond")
                requested.append(nearest)
        elif params["TLIST_TYPE"] == "'CAL'":
            requested = [input_tick(v) for v in labels]
        else:
            raise ValueError("Undeclared reference epoch encoding")
        if len(requested) != len(set(requested)):
            raise ValueError("Duplicate requested TT epoch")
        auxiliary = None
        guard = protocol.get("first_tlist_epoch_guard")
        if guard is not None:
            if (
                guard != {"method_id": "integer_jd_prefix_v1"}
                or params["TLIST_TYPE"] not in {"'JD'", "'MJD'", "'CAL'"}
                or len(requested) < 2
                or len(requested) > protocol["maximum_labels_per_batch"]
            ):
                raise ValueError("Changed first-TLIST-epoch guard protocol")
            auxiliary, requested = requested[0], requested[1:]
            minimum = min(Fraction(t, DAY_US) + Fraction(3442849, 2) for t in requested)
            expected_prefix = minimum.numerator // minimum.denominator - 1
            if Fraction(auxiliary, DAY_US) + Fraction(3442849, 2) != expected_prefix:
                raise ValueError(
                    "Auxiliary epoch is not the declared integer-JD prefix"
                )
        if "raw_file" in entry:
            raw = (material / entry["raw_file"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]:
                raise ValueError("Raw response changed")
        else:
            raw = b""
        if entry.get("http_status") != 200:
            raw_failures.append({k: v for k, v in entry.items() if k != "parameters"})
            continue
        if entry.get("raw_file") != anchored.get("raw_file") or entry.get(
            "raw_sha256"
        ) != anchored.get("raw_sha256"):
            raise ValueError("Raw provenance differs from immutable reference batch")
        for key in [
            "network_request_performed",
            "reused_raw_path",
            "reused_raw_sha256",
        ]:
            if entry.get(key) != anchored.get(key):
                raise ValueError("Raw recovery provenance changed")
        if (
            entry.get("reused_raw_sha256") is not None
            and entry["reused_raw_sha256"] != entry["raw_sha256"]
        ):
            raise ValueError("Recovery bytes differ from original response")
        try:
            response = json.loads(raw)
        except ValueError:
            raw_failures.append({"batch": entry["batch"], "error": "invalid JSON"})
            continue
        text = response.get("result", "")
        if response.get("error") or "$$SOE" not in text:
            raw_failures.append(
                {"batch": entry["batch"], "error": response.get("error")}
            )
            continue
        target_header = re.search(
            r"^Target body name:\s+.+?\s+\((\d+)\)", text, re.MULTILINE
        )
        if target_header is None or int(target_header[1]) != protocol["targets"][body]:
            raise ValueError("Returned target header changed")
        if not all(
            token in text
            for token in [
                "Center body name: Earth (399)",
                "ICRF",
                "Date__(TT)",
                f"({protocol['targets'][body]})",
            ]
        ):
            raise ValueError("Returned target/frame/time header changed")
        table = csv.reader(io.StringIO(text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]))
        received = set()
        auxiliary_rows = []
        rejected_epochs = []
        for columns in table:
            if not columns:
                continue
            printed_jd = Fraction(columns[1].strip())
            if auxiliary is not None and abs(
                printed_jd - Fraction(auxiliary, DAY_US) - Fraction(3442849, 2)
            ) <= Fraction(protocol["timestamp_printing_tolerance_days"]):
                if auxiliary_rows:
                    raise ValueError("Duplicate auxiliary integer-JD epoch")
                ra, dec = map(float, columns[-3:-1])
                if not all(math.isfinite(v) for v in (ra, dec)) or not -90 <= dec <= 90:
                    raise ValueError("Invalid auxiliary angles")
                auxiliary_rows.append(list(columns))
                continue
            candidates = [
                t
                for t in requested
                if abs(printed_jd - Fraction(t, DAY_US) - Fraction(3442849, 2))
                <= Fraction(protocol["timestamp_printing_tolerance_days"])
            ]
            if not candidates and protocol.get("retain_rejected_epoch_rows", False):
                rejected_epochs.append(
                    {
                        "returned_jd_tt_string": columns[1].strip(),
                        "reason": "outside_frozen_epoch_match_budget",
                    }
                )
                continue
            if len(candidates) != 1:
                raise ValueError("Returned JD is ambiguous or not requested")
            tick = candidates[0]
            if tick in received or (body, tick) in point_map:
                raise ValueError("Duplicate returned TT epoch")
            received.add(tick)
            ra, dec = map(float, columns[-3:-1])
            if not all(math.isfinite(v) for v in (ra, dec)) or not -90 <= dec <= 90:
                raise ValueError("Invalid independent angles")
            unit = precise_direction(ra, dec)
            point_map[(body, tick)] = (unit, columns, entry["batch"])
        if auxiliary is not None:
            expected_guard = {
                "method_id": "integer_jd_prefix_v1",
                "requested_jd": str(Fraction(auxiliary, DAY_US) + Fraction(3442849, 2)),
                "primary_requested_points": len(requested),
                "wire_requested_points": len(requested) + 1,
                "auxiliary_rows": auxiliary_rows,
                "auxiliary_used_in_position_or_rate_comparison": False,
            }
            if (
                len(auxiliary_rows) != 1
                or anchored.get("first_tlist_epoch_guard") != expected_guard
            ):
                raise ValueError("Auxiliary integer-JD coverage or declaration changed")
            auxiliary_batches_validated += 1
        if len(received) != batches[entry["batch"]]["returned_points"]:
            raise ValueError("Declared raw coverage changed")
        if protocol.get("retain_rejected_epoch_rows", False):
            if rejected_epochs != anchored.get("rejected_epoch_rows"):
                raise ValueError("Rejected epoch declaration changed")
            if rejected_epochs:
                raw_failures.append(
                    {"batch": entry["batch"], "rejected_epoch_rows": rejected_epochs}
                )
    if len(reference["rows"]) != len(protocol["cases"]):
        raise ValueError("Frozen case count changed")
    weights = interpolation_weights()
    failures = []
    available = probes = bc_probes = 0
    maximum = 0.0
    maximum_replay_ulps = 0.0
    for case, row in zip(protocol["cases"], reference["rows"]):
        if any(row.get(k) != v for k, v in case.items()):
            raise ValueError("Case identity changed")
        center = center_tick(case["date_tt"])
        if row["jd_tt"] != float(Fraction(center, DAY_US) + Fraction(3442849, 2)):
            raise ValueError("Center TT epoch changed")
        steps = protocol["steps_seconds"][case["body"]]
        offsets = sorted({k * h for h in steps for k in range(-6, 7)})
        explicit = protocol.get("explicit_offsets_seconds", {}).get(case["body"])
        if explicit is not None:
            if (
                not isinstance(explicit, list)
                or any(type(v) is not int for v in explicit)
                or explicit != sorted(set(explicit))
                or not set(offsets).issubset(explicit)
            ):
                raise ValueError("Invalid explicit reference node plan")
            offsets = explicit
        if set(row["samples"]) != set(map(str, offsets)):
            raise ValueError("Reference probe nodes changed")
        missing = []
        for offset in offsets:
            tick = center + offset * 1000000
            actual = point_map.get((case["body"], tick))
            stored = row["samples"][str(offset)]
            if actual is None:
                if stored is not None:
                    raise ValueError("Invented reference sample")
                missing.append(str(offset))
                continue
            if stored is None:
                raise ValueError("Omitted available raw probe")
            unit, columns, batch = actual
            maximum_replay_ulps = max(
                maximum_replay_ulps,
                check_stored_direction(stored["unit_direction"], unit),
            )
            if (
                stored["returned_jd_tt_string"] != columns[1].strip()
                or stored["returned_calendar_label_untrusted_without_JD"] != columns[0]
                or stored["raw_batch"] != batch
                or stored["printed_angles"] != [s.strip() for s in columns[-3:-1]]
                or input_tick(stored["requested_calendar_label"]) != tick
                or stored["ra_degrees"] != float(columns[-3])
                or stored["dec_degrees"] != float(columns[-2])
            ):
                raise ValueError("Frozen sample differs from raw material")
            probes += 1
            bc_probes += tick < DAY_US
        if missing != row["missing_offsets_seconds"]:
            raise ValueError("Missing-probe declaration changed")
        if missing:
            failures.append(
                {"id": case["id"], "reason": "missing_probes", "offsets": missing}
            )
            continue
        estimates = {}
        for h in steps:
            estimates[str(h)] = [
                math.fsum(
                    float(weights[k])
                    * (
                        row["samples"][str(k * h)]["unit_direction"][axis]
                        - row["samples"][str(-k * h)]["unit_direction"][axis]
                    )
                    for k in range(1, 7)
                )
                * 86400
                / h
                for axis in range(3)
            ]
        if estimates != row["derivatives_per_tt_day"]:
            raise ValueError("Reference derivative replay changed")
        difference = max(
            math.degrees(math.dist(a, b)) * 3600
            for a, b in combinations(estimates.values(), 2)
        )
        if difference != row["step_difference_arcsec_per_day"]:
            raise ValueError("Reference convergence declaration changed")
        maximum = max(maximum, difference)
        available += 1
        if difference > protocol["fixed_reference_convergence_arcsec_per_day"]:
            failures.append(
                {
                    "id": case["id"],
                    "reason": "step_nonconvergence",
                    "difference_arcsec_per_day": difference,
                }
            )
    result = {
        "status": (
            "reference_quality_unresolved"
            if failures
            else "declared_reference_quality_satisfied"
        ),
        "exit_code": 2 if failures else 0,
        "cases": len(protocol["cases"]),
        "complete_cases": available,
        "position_probes": probes,
        "BC_position_probes": bc_probes,
        "maximum_step_difference_arcsec_per_day": maximum,
        "failures": failures,
        "raw_failed_attempts": raw_failures,
        "stencil_moments_exact_degrees_0_through_12": True,
        "direction_arithmetic_replay": {
            "method": "independent_decimal_Taylor_replay_of_binary64_radian_inputs_v1",
            "decimal_digits": PRECISION,
            "component_representation_budget_ULPs": COMPONENT_ULP_BUDGET,
            "maximum_component_error_ULPs": maximum_replay_ulps,
            "physical_error_lines_changed": False,
            "scope": "Data-specific arithmetic replay only. The original exact-platform libm rejection is retained;not an ephemeris or observational error bound.",
        },
        "candidate_compared": False,
        "full_goal_complete": False,
    }
    if protocol.get("first_tlist_epoch_guard") is not None:
        result["first_tlist_epoch_guard"] = {
            "method_id": "integer_jd_prefix_v1",
            "batches_with_validated_auxiliary_epoch": auxiliary_batches_validated,
            "auxiliary_used_in_position_or_rate_comparison": False,
            "all_primary_nodes_and_fixed_lines_preserved": True,
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["protocol", "reference", "material", "seal", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = validate(args.protocol, args.reference, args.material, args.seal)
    with args.output.open("x") as handle:
        handle.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(result["exit_code"])
