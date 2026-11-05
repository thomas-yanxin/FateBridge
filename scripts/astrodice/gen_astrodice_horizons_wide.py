"""Collect frozen TT/ICRF wide references, retaining BC and missing probes.

No candidate or Swiss import. The returned JD column identifies output labels:
Horizons CSV calendar labels alone do not reliably distinguish BC from AD.
Matching that label does not certify the internal numerical evaluation epoch.
All raw responses and transport failures are journalled before interpretation.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import combinations
from pathlib import Path

DAY_US = 86400000000
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ticks(label):
    dt = datetime.fromisoformat(label)
    return dt.toordinal() * DAY_US + (
        (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000000 + dt.microsecond
    )


def julian_day(tick):
    return Fraction(tick, DAY_US) + Fraction(3442849, 2)


def julian_input_label(tick, *, modified=False):
    # One decimal conversion of the exact requested TT, avoiding the service's
    # calendar-parser path. This does not move the epoch or widen its budget.
    with localcontext() as context:
        context.prec = 60
        # MJD = JD - 2400000.5. Keep the offset exact before conversion;
        # neither encoding moves the requested integer-microsecond epoch.
        offset = Decimal("-678576" if modified else "1721424.5")
        return str(Decimal(tick) / Decimal(DAY_US) + offset)


def wire_epochs(protocol, requested):
    """An explicit, retained integer-JD prefix protects the primary epochs.

    The first TLIST epoch has exhibited a distinct precision path. This
    auxiliary observation never replaces a primary node or relaxes a line.
    """
    guard = protocol.get("first_tlist_epoch_guard")
    if guard is None:
        return list(requested), None
    if (
        guard != {"method_id": "integer_jd_prefix_v1"}
        or protocol["reference_parameters"]["TLIST_TYPE"]
        not in {"'JD'", "'MJD'", "'CAL'"}
        or not requested
        or protocol["maximum_labels_per_batch"] < 2
    ):
        raise ValueError("Invalid first-TLIST-epoch guard protocol")
    first = julian_day(min(requested))
    prefix_jd = first.numerator // first.denominator - 1
    tick = (Fraction(prefix_jd) - Fraction(3442849, 2)) * DAY_US
    if tick.denominator != 1:
        raise ValueError("Integer-JD guard is not an exact microsecond")
    return [int(tick), *requested], int(tick)


def calendar_label(tick):
    ordinal, micros = divmod(tick, DAY_US)
    cycle, remainder = divmod(ordinal - 1, 146097)
    representative = date.fromordinal(remainder + 1)
    year = representative.year + cycle * 400
    era, number = ("ad", year) if year > 0 else ("bc", 1 - year)
    seconds, microsecond = divmod(micros, 1000000)
    hour, remainder = divmod(seconds, 3600)
    minute, second = divmod(remainder, 60)
    return (
        f"{number}{era}-{MONTHS[representative.month - 1]}-{representative.day:02d} "
        f"{hour:02d}:{minute:02d}:{second:02d}.{microsecond:06d}"
    )


def weights():
    return {
        k: Fraction((-1) ** (k + 1), k)
        * Fraction(
            math.factorial(6) ** 2, math.factorial(6 - k) * math.factorial(6 + k)
        )
        for k in range(1, 7)
    }


def row_points(protocol):
    result = []
    for case in protocol["cases"]:
        center = ticks(case["date_tt"])
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
        result.append((case, center, offsets))
    return result


def collect(protocol_path, output, material, reuse_material=None):
    import certifi

    protocol = json.loads(protocol_path.read_text())
    if output.exists() or material.exists():
        raise FileExistsError("Never overwrite a first reference or raw journal")
    parameters = protocol.get("reference_parameters")
    if not isinstance(parameters, dict) or str(
        parameters.get("TIME_TYPE", "")
    ).strip().upper() not in {"TT", "'TT'"}:
        raise ValueError("Frozen observer collector requires explicit TIME_TYPE='TT'")
    recovery = {}
    recovery_assessment = []
    if reuse_material is not None:
        for line in (reuse_material / "requests.jsonl").read_text().splitlines():
            entry = json.loads(line)
            if entry.get("http_status") != 200 or "raw_file" not in entry:
                continue
            raw_path = reuse_material / entry["raw_file"]
            raw = raw_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]:
                raise ValueError("Recovery raw response identity changed")
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                payload = None
            text = payload.get("result") if isinstance(payload, dict) else None
            reusable = (
                isinstance(payload, dict)
                and not payload.get("error")
                and isinstance(text, str)
                and "$$SOE" in text
                and "$$EOE" in text
                and text.index("$$SOE") < text.index("$$EOE")
            )
            recovery_assessment.append(
                {
                    "original_raw_path": str(raw_path),
                    "original_raw_sha256": entry["raw_sha256"],
                    "status": (
                        "structurally_reusable_ephemeris"
                        if reusable
                        else "preserved_unavailable_response_not_reused"
                    ),
                    "source_accuracy_certified": False,
                }
            )
            if not reusable:
                continue
            key = json.dumps([entry["body"], entry["parameters"]], sort_keys=True)
            recovery[key] = (raw, str(raw_path), entry["raw_sha256"])
    material.mkdir()
    if reuse_material is not None:
        with (material / "recovery-cache-assessment.json").open("x") as handle:
            json.dump(recovery_assessment, handle, indent=2)
            handle.write("\n")
    context = ssl.create_default_context(cafile=certifi.where())
    known_points = {}
    batches = []
    journal = (material / "requests.jsonl").open("x")
    count = 0

    def request(body, requested):
        nonlocal count
        count += 1
        wire_requested, auxiliary = wire_epochs(protocol, requested)
        if len(wire_requested) > protocol["maximum_labels_per_batch"]:
            raise ValueError("Frozen wire-label budget exceeded")
        encoding = protocol["reference_parameters"]["TLIST_TYPE"]
        if encoding == "'JD'":
            formatter = julian_input_label
        elif encoding == "'MJD'":
            formatter = lambda t: julian_input_label(t, modified=True)
        elif encoding == "'CAL'":
            formatter = calendar_label
        else:
            raise ValueError("Unplanned reference epoch encoding")
        parameters = {
            **protocol["reference_parameters"],
            "COMMAND": f"'{protocol['targets'][body]}'",
            "TLIST": "\n".join(f"'{formatter(t)}'" for t in wire_requested),
        }
        url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(
            parameters
        )
        if len(url.encode()) > protocol["maximum_url_bytes"]:
            raise ValueError("Frozen request byte budget exceeded")
        record = {"batch": count, "body": body, "parameters": parameters}
        response = None
        for attempt in range(1, protocol["maximum_transport_attempts"] + 1):
            entry = {**record, "attempt": attempt}
            try:
                prior = recovery.get(json.dumps([body, parameters], sort_keys=True))
                if prior is not None:
                    raw, original_path, original_sha = prior
                    entry.update(
                        http_status=200,
                        network_request_performed=False,
                        reused_raw_path=original_path,
                        reused_raw_sha256=original_sha,
                    )
                else:
                    req = urllib.request.Request(
                        url,
                        headers={
                            "User-Agent": "FateBridge independent reference audit"
                        },
                    )
                    from scripts.astrodice.astrodice_horizons_transport import (
                        open_horizons,
                    )

                    with open_horizons(
                        req, timeout=40, context=context, receipt=entry
                    ) as received:
                        raw = received.read()
                        entry.update(
                            http_status=received.status, network_request_performed=True
                        )
            except Exception as error:
                entry.update(error_type=type(error).__name__, error=str(error))
                if isinstance(error, urllib.error.HTTPError):
                    raw = error.read()
                    name = f"batch-{count:04d}-attempt-{attempt}-http-error.txt"
                    (material / name).write_bytes(raw)
                    entry.update(
                        http_status=error.code,
                        raw_file=name,
                        raw_sha256=hashlib.sha256(raw).hexdigest(),
                    )
                journal.write(json.dumps(entry) + "\n")
                journal.flush()
                retryable = isinstance(error, (TimeoutError, urllib.error.URLError))
                if isinstance(error, urllib.error.HTTPError):
                    retryable = error.code in {429, 500, 502, 503, 504}
                if retryable and attempt < protocol["maximum_transport_attempts"]:
                    continue
                break
            else:
                name = f"batch-{count:04d}-attempt-{attempt}.json"
                (material / name).write_bytes(raw)
                entry.update(raw_file=name, raw_sha256=hashlib.sha256(raw).hexdigest())
                journal.write(json.dumps(entry) + "\n")
                journal.flush()
                record.update(entry)
                try:
                    response = json.loads(raw)
                except ValueError as error:
                    record["parse_error"] = str(error)
                break
        returned = {}
        auxiliary_rows = []
        rejected_epochs = []
        text = response.get("result", "") if response else ""
        if response and not response.get("error") and "$$SOE" in text:
            target_header = re.search(
                r"^Target body name:\s+.+?\s+\((\d+)\)", text, re.MULTILINE
            )
            if (
                target_header is None
                or int(target_header[1]) != protocol["targets"][body]
            ):
                raise ValueError("Unexpected returned target header")
            if not all(
                token in text
                for token in [
                    "Center body name: Earth (399)",
                    "ICRF",
                    "Date__(TT)",
                    f"({protocol['targets'][body]})",
                ]
            ):
                raise ValueError("Unexpected reference target/frame/time header")
            table = csv.reader(
                io.StringIO(text.split("$$SOE", 1)[1].split("$$EOE", 1)[0])
            )
            for columns in table:
                if not columns:
                    continue
                stamp = Fraction(columns[1].strip())
                if auxiliary is not None and abs(
                    stamp - julian_day(auxiliary)
                ) <= Fraction(protocol["timestamp_printing_tolerance_days"]):
                    if auxiliary_rows:
                        raise ValueError("Duplicate auxiliary epoch")
                    if not all(math.isfinite(float(v)) for v in columns[-3:-1]):
                        raise ValueError("Nonfinite auxiliary angle")
                    auxiliary_rows.append(list(columns))
                    continue
                candidates = [
                    t
                    for t in requested
                    if abs(stamp - julian_day(t))
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
                if len(candidates) != 1 or candidates[0] in returned:
                    raise ValueError("Ambiguous, duplicate or unexpected TT JD")
                tick = candidates[0]
                ra, dec = map(float, columns[-3:-1])
                if not all(math.isfinite(v) for v in (ra, dec)):
                    raise ValueError("Nonfinite independent reference angle")
                alpha, delta = map(math.radians, (ra, dec))
                returned[tick] = {
                    "requested_calendar_label": calendar_label(tick),
                    "returned_calendar_label_untrusted_without_JD": columns[0],
                    "returned_jd_tt_string": columns[1].strip(),
                    "ra_degrees": ra,
                    "dec_degrees": dec,
                    "printed_angles": [v.strip() for v in columns[-3:-1]],
                    "unit_direction": [
                        math.cos(delta) * math.cos(alpha),
                        math.cos(delta) * math.sin(alpha),
                        math.sin(delta),
                    ],
                    "raw_batch": count,
                }
            if auxiliary is not None and len(auxiliary_rows) != 1:
                raise ValueError(
                    "Auxiliary integer-JD epoch missing or outside fixed line"
                )
        record.update(
            returned_points=len(returned),
            requested_points=len(requested),
            reference_error=(response or {}).get("error"),
        )
        if protocol.get("retain_rejected_epoch_rows", False):
            record["rejected_epoch_rows"] = rejected_epochs
        if auxiliary is not None:
            record["first_tlist_epoch_guard"] = {
                "method_id": "integer_jd_prefix_v1",
                "requested_jd": str(julian_day(auxiliary)),
                "primary_requested_points": len(requested),
                "wire_requested_points": len(wire_requested),
                "auxiliary_rows": auxiliary_rows,
                "auxiliary_used_in_position_or_rate_comparison": False,
            }
        batches.append(record)
        for tick in requested:
            known_points[(body, tick)] = returned.get(tick)
        print(
            f"Reference batch{count} {body}: {len(returned)}/{len(requested)}",
            flush=True,
        )

    plans = row_points(protocol)
    try:
        # Documented upper-bound probes are requested individually. Their
        # failure cannot suppress valid neighbouring or unrelated epochs.
        for body in protocol["targets"]:
            normal = sorted(
                {
                    center + offset * 1000000
                    for case, center, offsets in plans
                    if case["body"] == body and not case.get("service_boundary_probe")
                    for offset in offsets
                }
            )
            size = protocol["maximum_labels_per_batch"] - int(
                protocol.get("first_tlist_epoch_guard") is not None
            )
            if size < 1:
                raise ValueError("No room for primary epochs in frozen batch budget")
            for start in range(0, len(normal), size):
                request(body, normal[start : start + size])
        for case, center, offsets in plans:
            if case.get("service_boundary_probe"):
                for offset in offsets:
                    request(case["body"], [center + offset * 1000000])
    finally:
        journal.close()
    rows = []
    w = weights()
    for case, center, offsets in plans:
        samples = {
            str(o): known_points[(case["body"], center + o * 1000000)] for o in offsets
        }
        missing = [o for o, point in samples.items() if point is None]
        rates = {}
        if not missing:
            for h in protocol["steps_seconds"][case["body"]]:
                rates[str(h)] = [
                    math.fsum(
                        float(w[k])
                        * (
                            samples[str(k * h)]["unit_direction"][axis]
                            - samples[str(-k * h)]["unit_direction"][axis]
                        )
                        for k in range(1, 7)
                    )
                    * 86400
                    / h
                    for axis in range(3)
                ]
        rows.append(
            {
                **case,
                "jd_tt": float(julian_day(center)),
                "samples": samples,
                "missing_offsets_seconds": missing,
                "derivatives_per_tt_day": rates,
                "step_difference_arcsec_per_day": (
                    max(
                        math.degrees(math.dist(a, b)) * 3600
                        for a, b in combinations(rates.values(), 2)
                    )
                    if rates
                    else None
                ),
            }
        )
    forbidden = [
        name
        for name in sys.modules
        if name == "swisseph" or name == "fatebridge" or name.startswith("fatebridge.")
    ]
    if forbidden:
        raise ValueError("Independent collection imported the candidate")
    result = {
        "protocol_sha256": digest(protocol_path),
        "collector_sha256": digest(Path(__file__)),
        "candidate_imported": False,
        "Swiss_imported": False,
        "returned_epoch_identity": {
            "role": "returned_label_matching_only",
            "label_match_budget_days": protocol["timestamp_printing_tolerance_days"],
            "numerical_evaluation_epoch_certified": False,
            "observer_TT_to_source_TDB_mapping_certified": False,
        },
        "batches": batches,
        "rows": rows,
        "scope": protocol["scope"],
    }
    with output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["protocol", "output", "material"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--reuse-material", type=Path)
    args = parser.parse_args()
    collect(args.protocol, args.output, args.material, args.reuse_material)
