"""Replay position-only quantities 1/12/45, never inventing a rate reference."""

import csv
import hashlib
import io
import json
import math
import re
from fractions import Fraction as Q

from scripts.astrodice_reference_math import check_stored_direction, precise_direction
from scripts.audit_astrodice_horizons_wide_reference import (
    DAY_US,
    center_tick,
    input_tick,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(protocol_path, reference_path, material):
    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    if (
        not protocol["position_only"]
        or protocol["rate_accuracy_assessed"]
        or protocol["fixed_position_arcsec"] != 0.02
        or protocol["fixed_rate_arcsec_per_day"] != 0.002
        or Q(protocol["timestamp_printing_tolerance_days"]) != Q(1, 10**9)
        or protocol["reference_parameters"]["QUANTITIES"] != "'1,12,45'"
        or any(value for value in protocol["steps_seconds"].values())
        or any(value != [0] for value in protocol["explicit_offsets_seconds"].values())
        or reference["protocol_sha256"] != digest(protocol_path)
        or reference["candidate_imported"]
        or reference["Swiss_imported"]
    ):
        raise ValueError("Position-only protocol or source identity changed")
    entries = [
        json.loads(line)
        for line in (material / "requests.jsonl").read_text().splitlines()
    ]
    batches = {row["batch"]: row for row in reference["batches"]}
    observed, rejected, unavailable = {}, [], []
    for entry in entries:
        anchor = batches[entry["batch"]]
        params, body = entry["parameters"], entry["body"]
        if (
            anchor["parameters"] != params
            or anchor["body"] != body
            or any(
                params.get(k) != v for k, v in protocol["reference_parameters"].items()
            )
            or params["COMMAND"] != f"'{protocol['targets'][body]}'"
        ):
            raise ValueError("Returned request parameters differ from frozen protocol")
        labels = re.findall(r"'([^']+)'", params["TLIST"])
        encoding = params["TLIST_TYPE"]
        if encoding not in {"'JD'", "'MJD'"}:
            raise ValueError("Undeclared position-reference encoding")
        origin = Q(3442849, 2) if encoding == "'JD'" else Q(-678576)
        wire = []
        for label in labels:
            tick = (Q(label) - origin) * DAY_US
            nearest = round(tick)
            if abs(tick - nearest) > Q(1, 10**30):
                raise ValueError("Numeric input lost its exact requested microsecond")
            wire.append(nearest)
        if (
            protocol["first_tlist_epoch_guard"] != {"method_id": "integer_jd_prefix_v1"}
            or not 2 <= len(wire) <= protocol["maximum_labels_per_batch"]
        ):
            raise ValueError("First-epoch guard changed")
        auxiliary, primary = wire[0], wire[1:]
        minimum = min(Q(t, DAY_US) + Q(3442849, 2) for t in primary)
        if (
            Q(auxiliary, DAY_US) + Q(3442849, 2)
            != minimum.numerator // minimum.denominator - 1
        ):
            raise ValueError("Auxiliary integer-JD epoch moved")
        if "raw_file" not in entry:
            unavailable.append(entry)
            continue
        raw_path = material / entry["raw_file"]
        if digest(raw_path) != entry["raw_sha256"]:
            raise ValueError("Raw position response changed")
        if entry.get("http_status") != 200:
            unavailable.append(entry)
            continue
        if (
            anchor.get("raw_sha256") != entry["raw_sha256"]
            or anchor.get("raw_file") != entry["raw_file"]
        ):
            raise ValueError("First response provenance changed")
        response = json.loads(raw_path.read_bytes())
        text = response.get("result", "")
        if response.get("error") or "$$SOE" not in text:
            unavailable.append(entry)
            continue
        target = re.search(
            r"^Target body name:\s+.+?\s+\((\d+)\).*?source: DE441", text, re.MULTILINE
        )
        if (
            target is None
            or int(target[1]) != protocol["targets"][body]
            or any(
                token not in text
                for token in [
                    "Center body name: Earth (399)",
                    "Date__(TT)",
                    "R.A.___(ICRF)",
                    "RA_(ICRF-a-app)",
                    "ang-sep, vis.",
                ]
            )
        ):
            raise ValueError(
                "Position source, frame, quantities or clock identity changed"
            )
        returned, aux_count, bad = {}, 0, []
        for row in csv.reader(io.StringIO(text.split("$$SOE")[1].split("$$EOE")[0])):
            if not row or not row[0].strip():
                continue
            if len(row) != 11 or row[-1].strip():
                raise ValueError("Quantity column contract changed")
            stamp = Q(row[1].strip())
            if abs(stamp - Q(auxiliary, DAY_US) - Q(3442849, 2)) <= Q(1, 10**9):
                aux_count += 1
                continue
            candidates = [
                t
                for t in primary
                if abs(stamp - Q(t, DAY_US) - Q(3442849, 2)) <= Q(1, 10**9)
            ]
            if not candidates:
                bad.append(
                    {
                        "returned_jd_tt_string": row[1].strip(),
                        "reason": "outside_frozen_epoch_match_budget",
                    }
                )
                continue
            if len(candidates) != 1 or candidates[0] in returned:
                raise ValueError("Ambiguous or duplicate returned primary epoch")
            tick = candidates[0]
            astrometric, apparent = [v.strip() for v in row[4:6]], [
                v.strip() for v in row[8:10]
            ]
            for values in [astrometric, apparent]:
                precise_direction(*map(float, values))
            if (
                row[7].strip() not in {"t", "O", "o", "p", "P", "u", "U", "-", "*"}
                or not math.isfinite(float(row[6]))
                or float(row[6]) < 0
            ):
                raise ValueError("Invalid primary separation or visibility")
            returned[tick] = {
                "astrometric_printed_angles": astrometric,
                "apparent_printed_angles": apparent,
                "primary_separation_arcsec": row[6].strip(),
                "primary_visibility_code": row[7].strip(),
                "primary_visibility_code_documented_exactly": row[7].strip() != "o",
                "returned_jd_tt_string": row[1].strip(),
                "raw_batch": entry["batch"],
            }
        if (
            aux_count != 1
            or len(returned) != anchor["returned_points"]
            or bad != anchor["rejected_epoch_rows"]
        ):
            raise ValueError("Position coverage or rejected epochs changed")
        rejected.extend({"batch": entry["batch"], **value} for value in bad)
        for tick, point in returned.items():
            key = body, tick
            if key in observed:
                raise ValueError("Duplicate independently returned observation")
            observed[key] = point
    if len(reference["rows"]) != len(protocol["cases"]):
        raise ValueError("Planned condition count changed")
    rows = []
    for case, stored in zip(protocol["cases"], reference["rows"]):
        if (
            any(stored.get(k) != v for k, v in case.items())
            or set(stored["samples"]) != {"0"}
            or stored["derivatives_per_tt_day"] != {}
            or stored["step_difference_arcsec_per_day"] is not None
        ):
            raise ValueError(
                "Position-only case was changed, dropped or given a hidden rate"
            )
        tick = center_tick(case["date_tt"])
        if stored["jd_tt"] != float(Q(tick, DAY_US) + Q(3442849, 2)):
            raise ValueError("Native numeric argument changed")
        point = observed.get((case["body"], tick))
        sample = stored["samples"]["0"]
        if point is None:
            if sample is not None or stored["missing_offsets_seconds"] != ["0"]:
                raise ValueError("Unavailable position was invented")
            rows.append(
                {**case, "status": "reference_unavailable", "observation": None}
            )
            continue
        if (
            sample is None
            or sample["printed_angles"] != point["apparent_printed_angles"]
            or sample["returned_jd_tt_string"] != point["returned_jd_tt_string"]
            or sample["raw_batch"] != point["raw_batch"]
            or input_tick(sample["requested_calendar_label"]) != tick
            or stored["missing_offsets_seconds"]
        ):
            raise ValueError("Stored position differs from immutable raw response")
        check_stored_direction(
            sample["unit_direction"],
            precise_direction(*map(float, point["apparent_printed_angles"])),
        )
        rows.append(
            {**case, "status": "position_reference_replayed", "observation": point}
        )
    return {
        "protocol_sha256": digest(protocol_path),
        "reference_sha256": digest(reference_path),
        "rows": rows,
        "rejected_epoch_rows": rejected,
        "unavailable_attempts": unavailable,
        "rate_accuracy_assessed": False,
        "candidate_accuracy_assessed": False,
        "full_goal_complete": False,
    }
